"""LangGraph StateGraph implementing the 5-step deterministic control plane.

input_guard -> router -> {direct_response | rag_retrieve->rag_compose | intake_tool | status_mgr | (preset)}
            -> tool_validator -> execute_tool | circuit_breaker -> hitl_gate (interrupt) -> finalize -> END
"""
from __future__ import annotations

import hashlib
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ..domain.enums import AuditAction
from ..domain.errors import FieldError, label
from ..domain.guards import PII_BLOCK_TEMPLATE, REFUSAL_TEMPLATE
from ..persistence.repository import Repository
from ..tools.circuit_breaker import HALT_MESSAGE, CircuitBreaker
from ..tools.registry import PreparedCall, ToolExecutor
from .router import Route, extract_intake_call, extract_status_call, route_text
from .state import TURN_DEFAULTS, AgentState

HELP_TEXT = (
    "Hello - I'm the deterministic intake & triage assistant (training prototype, fictional data only).\n\n"
    "I can:\n"
    "- **Search history & SOPs** (hybrid RAG): e.g. *any history of difficulty breathing with LOT-88392?*\n"
    "- **Update status**: *move REF-2026-0001 to in review* / *close REF-2026-0001* (closure needs HITL approval)\n"
    "- **Look up a report**: *show REF-2026-0001*\n"
    "- **Submit a report**: use the New Report page, or *new report: type=PQC; product=Placebrix 5mg; "
    "lot=LOT-10457; received=2026-11-21; reporter=Pharmacist; description=...*\n\n"
    "I never assess causality, recommend treatment or decide reportability."
)


def _trace(state: AgentState, thought: str, action: str, observation: str) -> list[dict[str, str]]:
    trace = list(state.get("react_trace") or [])
    trace.append({"step": str(len(trace) + 1), "thought": thought, "action": action, "observation": observation})
    return trace


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _fmt_errors(errors: list[dict[str, Any]]) -> str:
    return "\n".join(f"- **{label(e['field']) if e['field'] not in ('_', '_tool') else 'Request'}**: {e['message']}"
                     for e in errors)


def _prepared_from(d: dict[str, Any]) -> PreparedCall:
    return PreparedCall(tool=d["tool"], raw_tool=d["raw_tool"], args=d["args"], ok=d["ok"],
                        repairs=list(d.get("repairs", [])),
                        errors=[FieldError(**e) for e in d.get("errors", [])])


def _prepared_to(p: PreparedCall) -> dict[str, Any]:
    return {"tool": p.tool, "raw_tool": p.raw_tool, "args": p.args, "ok": p.ok, "repairs": p.repairs,
            "errors": [e.to_dict() for e in p.errors]}


def build_graph(executor: ToolExecutor, repo: Repository, checkpointer: BaseCheckpointSaver):
    # ------------------------------------------------------------------ nodes
    def input_guard(state: AgentState) -> dict[str, Any]:
        upd: dict[str, Any] = dict(TURN_DEFAULTS)
        text = state.get("user_input")
        actor = state.get("actor_id", "OP-01")
        if text:
            upd["messages"] = [{"role": "user", "content": text}]
        breaker = CircuitBreaker.from_dict(state.get("breaker"))
        upd["breaker"] = breaker.to_dict()
        if breaker.is_open:
            upd.update(route=Route.HALTED, route_rule="BREAKER_OPEN", route_reason="circuit breaker is open",
                       halted=True)
            upd["react_trace"] = _trace(upd, "Circuit breaker is OPEN for this session.", "halt",
                                        "execution refused before routing")
            return upd
        if state.get("preset_call"):
            upd["react_trace"] = _trace(upd, "Structured UI call - free-text guards not needed "
                                             "(Pydantic schemas include the PII shield).", "pass",
                                        f"tool={state['preset_call'].get('tool')}")
            return upd
        decision = route_text(text)
        if decision.route in (Route.PII_BLOCKED, Route.OUT_OF_SCOPE):
            repo.record_event(actor, AuditAction.REQUEST_REFUSED, details={
                "rule": decision.rule, "category": decision.detail[:80], "input_sha256": _sha(text or "")})
            upd.update(route=decision.route, route_rule=decision.rule, route_reason=decision.reason)
        upd["react_trace"] = _trace(upd, "Screen input for personal identifiers and clinical-decision requests.",
                                    "input_guard(PII shield, non-clinical scope filter)",
                                    f"blocked: {decision.rule}" if upd["route"] else "clean")
        return upd

    def router(state: AgentState) -> dict[str, Any]:
        if state.get("route"):
            return {}
        if state.get("preset_call"):
            pc = state["preset_call"]
            return {"route": Route.TOOL, "route_rule": "R_PRESET", "route_reason": "structured UI action",
                    "tool_call": {"tool": pc["tool"], "args": dict(pc.get("args") or {})},
                    "react_trace": _trace(state, "Input is a structured UI action; route straight to validation.",
                                          f"route -> {Route.TOOL}", f"tool={pc['tool']}")}
        d = route_text(state.get("user_input"))
        return {"route": d.route, "route_rule": d.rule, "route_reason": d.reason,
                "react_trace": _trace(state, f"Router: matched rule {d.rule} ({d.reason}).",
                                      f"route -> {d.route}", "deterministic routing complete")}

    def direct_response(state: AgentState) -> dict[str, Any]:
        route = state.get("route")
        if route == Route.HALTED:
            msg = HALT_MESSAGE
        elif route == Route.PII_BLOCKED:
            msg = PII_BLOCK_TEMPLATE.format(categories=route_text(state.get("user_input")).detail or "personal data")
        elif route == Route.OUT_OF_SCOPE:
            msg = REFUSAL_TEMPLATE.format(category=route_text(state.get("user_input")).detail or "that request")
        else:
            msg = HELP_TEXT
        return {"response": msg, "react_trace": _trace(state, "No tool or retrieval needed.", "direct_response",
                                                      f"{route} template returned")}

    def intake_tool(state: AgentState) -> dict[str, Any]:
        call = extract_intake_call(state.get("user_input") or "", state.get("actor_id", "OP-01"))
        keys = sorted(k for k in call["args"] if k != "actor_id")
        return {"tool_call": call, "react_trace": _trace(
            state, "Parse key=value pairs from the message into submit_intake_report arguments.",
            "extract_intake_call", f"keys found: {', '.join(keys) or 'none'}")}

    def status_mgr(state: AgentState) -> dict[str, Any]:
        call = extract_status_call(state.get("user_input") or "", state.get("actor_id", "OP-01"))
        return {"tool_call": call, "react_trace": _trace(
            state, "Extract reference id and target status from the workflow request.",
            f"extract_status_call -> {call['tool']}", f"args: {call['args']}")}

    def tool_validator(state: AgentState) -> dict[str, Any]:
        call = state["tool_call"] or {}
        prepared = executor.prepare(call.get("tool", ""), call.get("args"))
        upd: dict[str, Any] = {"prepared": _prepared_to(prepared)}
        obs = "valid" if prepared.ok else f"{len(prepared.errors)} validation error(s)"
        if prepared.repairs:
            obs += f"; auto-repairs: {'; '.join(prepared.repairs)}"
        if not prepared.ok:
            breaker = CircuitBreaker.from_dict(state.get("breaker"))
            executor.register_failure(prepared, prepared.errors, breaker, state.get("actor_id", "OP-01"))
            upd["breaker"] = breaker.to_dict()
            upd["errors"] = [e.to_dict() for e in prepared.errors]
        upd["react_trace"] = _trace(state, "Validate tool call against the strict Pydantic schema (with auto-repair).",
                                    f"validate({prepared.tool})", obs)
        return upd

    def execute_tool(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        prepared = _prepared_from(state["prepared"])
        result = executor.execute(prepared)
        breaker = CircuitBreaker.from_dict(state.get("breaker"))
        upd: dict[str, Any] = {"result": result.to_dict()}
        if not result.ok:
            executor.register_failure(prepared, result.errors, breaker, state.get("actor_id", "OP-01"))
            upd["errors"] = [e.to_dict() for e in result.errors]
            obs = f"rejected by domain rules: {result.errors[0].code}"
        else:
            breaker.record_success()
            data = result.data or {}
            obs = "success"
            if data.get("hitl_required"):
                thread_id = config.get("configurable", {}).get("thread_id", "")
                repo.set_approval_thread(data["approval_id"], thread_id)
                upd["pending_approval"] = {"approval_id": data["approval_id"], "ref_id": data["ref_id"],
                                           "requested_by": state.get("actor_id"), "thread_id": thread_id}
                obs = f"HITL required - approval #{data['approval_id']} created (PENDING)"
            if prepared.tool == "search_knowledge":
                upd["retrieval"] = data
        upd["breaker"] = breaker.to_dict()
        upd["react_trace"] = _trace(state, "Execute the validated call through its LangChain StructuredTool.",
                                    f"{prepared.tool}({', '.join(f'{k}={v}' for k, v in prepared.args.items() if k in ('ref_id', 'target_status', 'batch_id', 'report_type', 'approval_id'))})",
                                    obs)
        return upd

    def circuit_breaker(state: AgentState) -> dict[str, Any]:
        breaker = CircuitBreaker.from_dict(state.get("breaker"))
        if breaker.is_open:
            return {"halted": True, "response": HALT_MESSAGE, "react_trace": _trace(
                state, f"Same invalid call seen {breaker.consecutive_failures} consecutive times "
                       f"(> {breaker.max_failures}).", "circuit_breaker -> OPEN", "execution halted")}
        errs = state.get("errors") or []
        repairs = (state.get("prepared") or {}).get("repairs") or []
        msg = "I couldn't complete that request:\n\n" + _fmt_errors(errs)
        if repairs:
            msg += "\n\n_Auto-repairs applied: " + "; ".join(repairs) + "_"
        msg += (f"\n\n_Invalid attempt {breaker.consecutive_failures} of {breaker.max_failures} allowed for "
                "this exact call - repeating it unchanged again will trip the circuit breaker._")
        return {"response": msg, "react_trace": _trace(
            state, "Return structured validation errors so the user can correct the input.",
            "circuit_breaker -> CLOSED (count)", f"consecutive_failures={breaker.consecutive_failures}")}

    def respond(state: AgentState) -> dict[str, Any]:
        res = state.get("result") or {}
        data = res.get("data") or {}
        tool = res.get("tool")
        if tool == "submit_intake_report":
            msg = f"Report **{data['ref_id']}** created with status **{data['status']}**."
        elif tool == "update_status":
            msg = f"**{data['ref_id']}** moved **{data.get('from_status')} -> {data['status']}**."
        elif tool == "get_report":
            msg = (f"**{data['ref_id']}** - {data['report_type']} - {data['product_name']} ({data['batch_id']}) - "
                   f"status **{data['status']}**, received {data['date_received']}.")
        else:
            msg = "Done."
        if res.get("repairs"):
            msg += "\n\n_Auto-repairs applied: " + "; ".join(res["repairs"]) + "_"
        return {"response": msg}

    def hitl_gate(state: AgentState) -> dict[str, Any]:
        pending = state["pending_approval"]
        decision = interrupt({
            "type": "hitl_closure_approval", "approval_id": pending["approval_id"], "ref_id": pending["ref_id"],
            "requested_by": pending["requested_by"],
            "message": f"Closure of {pending['ref_id']} requires reviewer approval (In Review -> Closed).",
        })
        breaker = CircuitBreaker.from_dict(state.get("breaker"))
        result = executor.call("decide_approval", {
            "approval_id": pending["approval_id"], "reviewer_id": decision.get("reviewer_id"),
            "decision": decision.get("decision"), "justification": decision.get("justification")},
            breaker, actor_id=decision.get("reviewer_id") or "UNKNOWN")
        upd: dict[str, Any] = {"breaker": breaker.to_dict(), "result": result.to_dict(), "halted": result.halted}
        if result.ok:
            d = result.data or {}
            upd["pending_approval"] = None
            upd["response"] = (f"Reviewer **{decision.get('reviewer_id')}** {d['decision'].lower()} closure of "
                               f"**{d['ref_id']}** - status is now **{d['status']}**.")
            obs = f"{d['decision']} -> status {d['status']}"
        else:
            upd["errors"] = [e.to_dict() for e in result.errors]
            upd["response"] = (result.message if result.halted else
                               "Decision not recorded - the request stays frozen:\n\n" +
                               _fmt_errors(upd["errors"]))
            obs = "decision rejected; gate re-armed" if not result.halted else "breaker open"
        upd["react_trace"] = _trace(state, "Human reviewer decision received; record it via decide_approval.",
                                    "hitl_gate(resume) -> decide_approval", obs)
        return upd

    def rag_retrieve(state: AgentState) -> dict[str, Any]:
        query = state.get("user_input") or ""
        return {"tool_call": {"tool": "search_knowledge", "args": {"query": query}},
                "react_trace": _trace(state, "Historical/SOP question -> run 4-stage hybrid retrieval.",
                                      "search_knowledge(query)", "dispatched to validator")}

    def rag_compose(state: AgentState) -> dict[str, Any]:
        r = state.get("retrieval") or {}
        repo.record_event(state.get("actor_id", "OP-01"), AuditAction.RAG_QUERY, details={
            "query_sha256": _sha(r.get("query", "")), "bm25_hits": len(r.get("bm25", [])),
            "dense_hits": len(r.get("dense", [])), "fused": len(r.get("fused", [])),
            "final": len(r.get("final", [])), "abstained": bool(r.get("abstained")),
            "citations": r.get("citations", [])[:5]})
        return {"response": r.get("answer", ""), "react_trace": _trace(
            state, "Compose an extractive, cited answer from chunks above the 0.40 rerank threshold.",
            "extractive_composer", f"abstained={r.get('abstained')}; citations={r.get('citations')}")}

    def finalize(state: AgentState) -> dict[str, Any]:
        return {"messages": [{"role": "assistant", "content": state.get("response", "")}]}

    # ------------------------------------------------------------------ edges
    def after_router(state: AgentState) -> str:
        r = state.get("route")
        if r in Route.DIRECT:
            return "direct_response"
        return {Route.RAG: "rag_retrieve", Route.INTAKE: "intake_tool", Route.STATUS: "status_mgr",
                Route.TOOL: "tool_validator"}[r]

    def after_validator(state: AgentState) -> str:
        return "execute_tool" if (state.get("prepared") or {}).get("ok") else "circuit_breaker"

    def after_execute(state: AgentState) -> str:
        res = state.get("result") or {}
        if not res.get("ok"):
            return "circuit_breaker"
        if state.get("pending_approval"):
            return "hitl_gate"
        if res.get("tool") == "search_knowledge":
            return "rag_compose"
        return "respond"

    def after_hitl(state: AgentState) -> str:
        if state.get("halted") or not state.get("pending_approval"):
            return "finalize"
        return "hitl_gate"  # decision invalid -> stay frozen, interrupt again

    g = StateGraph(AgentState)
    for name, fn in [("input_guard", input_guard), ("router", router), ("direct_response", direct_response),
                     ("intake_tool", intake_tool), ("status_mgr", status_mgr), ("tool_validator", tool_validator),
                     ("execute_tool", execute_tool), ("circuit_breaker", circuit_breaker), ("respond", respond),
                     ("hitl_gate", hitl_gate), ("rag_retrieve", rag_retrieve), ("rag_compose", rag_compose),
                     ("finalize", finalize)]:
        g.add_node(name, fn)
    g.add_edge(START, "input_guard")
    g.add_edge("input_guard", "router")
    g.add_conditional_edges("router", after_router,
                            ["direct_response", "rag_retrieve", "intake_tool", "status_mgr", "tool_validator"])
    g.add_edge("intake_tool", "tool_validator")
    g.add_edge("status_mgr", "tool_validator")
    g.add_edge("rag_retrieve", "tool_validator")
    g.add_conditional_edges("tool_validator", after_validator, ["execute_tool", "circuit_breaker"])
    g.add_conditional_edges("execute_tool", after_execute, ["circuit_breaker", "hitl_gate", "rag_compose", "respond"])
    g.add_conditional_edges("hitl_gate", after_hitl, ["hitl_gate", "finalize"])
    for n in ("direct_response", "circuit_breaker", "respond", "rag_compose"):
        g.add_edge(n, "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)

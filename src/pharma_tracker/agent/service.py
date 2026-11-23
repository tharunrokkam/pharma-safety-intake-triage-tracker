"""AgentService - one facade used by the Streamlit pages, scripts and integration tests.

Owns: Repository (long-term memory), HybridRAGPipeline, ToolExecutor and the compiled LangGraph graph
with an InMemorySaver checkpointer (short-term memory, one thread per UI session / workflow).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from ..config import db_path as default_db_path
from ..persistence.repository import Repository
from ..rag.indexer import add_report, build_index, make_pipeline
from ..rag.pipeline import HybridRAGPipeline
from ..tools.circuit_breaker import CircuitBreaker
from ..tools.registry import ToolExecutor
from .graph import build_graph


@dataclass
class TurnResult:
    thread_id: str
    next_thread_id: str
    response: str = ""
    route: str = ""
    route_rule: str = ""
    route_reason: str = ""
    trace: list[dict[str, str]] = field(default_factory=list)
    retrieval: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    halted: bool = False
    interrupted: bool = False
    interrupt_payload: dict[str, Any] | None = None
    breaker: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.result and self.result.get("ok")) and not self.errors


def new_thread_id() -> str:
    return f"t-{uuid.uuid4().hex[:12]}"


class AgentService:
    def __init__(self, db_path: Path | str | None = None, pipeline: HybridRAGPipeline | None = None,
                 rag_mode: str | None = None, write_manifest: bool = False):
        self.repo = Repository(db_path or default_db_path())
        self.pipeline = pipeline or make_pipeline(rag_mode)
        build_index(self.repo, self.pipeline, write_manifest=write_manifest)
        self.executor = ToolExecutor(
            self.repo,
            search_fn=lambda q: self.pipeline.search(q).to_dict(),
            on_report_created=lambda ref: add_report(self.repo, self.pipeline, ref),
        )
        self.checkpointer = InMemorySaver()
        self.graph = build_graph(self.executor, self.repo, self.checkpointer)

    # ------------------------------------------------------------------ invocation helpers
    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    def _snapshot_result(self, thread_id: str) -> TurnResult:
        snap = self.graph.get_state(self._config(thread_id))
        v = snap.values or {}
        interrupts = list(getattr(snap, "interrupts", ()) or ())
        payload = interrupts[0].value if interrupts else None
        interrupted = bool(interrupts)
        response = v.get("response", "")
        if interrupted and payload:
            response = (f"{response}\n\n" if response else "") + (
                f"**Human-in-the-loop gate:** {payload['message']} Approval #{payload['approval_id']} is "
                "PENDING in *Triage Approvals*; the report stays **In Review** (frozen) until a different "
                "reviewer approves or rejects it.")
        return TurnResult(
            thread_id=thread_id,
            # An interrupted thread now belongs to the approval workflow; the session continues on a new one.
            next_thread_id=new_thread_id() if interrupted else thread_id,
            response=response, route=v.get("route", ""), route_rule=v.get("route_rule", ""),
            route_reason=v.get("route_reason", ""), trace=list(v.get("react_trace") or []),
            retrieval=v.get("retrieval"), result=v.get("result"), errors=list(v.get("errors") or []),
            halted=bool(v.get("halted")), interrupted=interrupted, interrupt_payload=payload,
            breaker=dict(v.get("breaker") or {}),
        )

    def _invoke(self, thread_id: str, payload: dict[str, Any]) -> TurnResult:
        self.graph.invoke(payload, self._config(thread_id))
        return self._snapshot_result(thread_id)

    # ------------------------------------------------------------------ public API
    def chat(self, thread_id: str, text: str, actor_id: str) -> TurnResult:
        return self._invoke(thread_id, {"user_input": text, "actor_id": actor_id, "preset_call": None})

    def run_tool(self, thread_id: str, tool: str, args: dict[str, Any], actor_id: str) -> TurnResult:
        return self._invoke(thread_id, {"user_input": None, "actor_id": actor_id,
                                        "preset_call": {"tool": tool, "args": args}})

    def submit_report(self, thread_id: str, fields: dict[str, Any], actor_id: str) -> TurnResult:
        return self.run_tool(thread_id, "submit_intake_report", {**fields, "actor_id": actor_id}, actor_id)

    def update_status(self, thread_id: str, ref_id: str, target_status: str, actor_id: str) -> TurnResult:
        return self.run_tool(thread_id, "update_status",
                             {"ref_id": ref_id, "target_status": target_status, "actor_id": actor_id}, actor_id)

    def has_live_interrupt(self, thread_id: str | None) -> bool:
        if not thread_id:
            return False
        try:
            snap = self.graph.get_state(self._config(thread_id))
        except Exception:  # noqa: BLE001 - unknown thread
            return False
        return bool(getattr(snap, "interrupts", ()))

    def decide_approval(self, approval_id: int, reviewer_id: str, decision: str, justification: str) -> TurnResult:
        """Resume the frozen LangGraph thread when it is live; otherwise (e.g. after an app restart wiped the
        volatile checkpointer) record the decision directly through the same validated tool."""
        ap = self.repo.get_approval(approval_id)
        resume = {"reviewer_id": reviewer_id, "decision": decision, "justification": justification}
        thread = (ap or {}).get("thread_id")
        if ap and self.has_live_interrupt(thread):
            self.graph.invoke(Command(resume=resume), self._config(thread))
            res = self._snapshot_result(thread)
            res.next_thread_id = thread
            return res
        breaker = CircuitBreaker()
        result = self.executor.call("decide_approval", {"approval_id": approval_id, **resume}, breaker,
                                    actor_id=reviewer_id)
        tid = thread or "direct"
        if result.ok:
            d = result.data or {}
            msg = (f"Reviewer **{reviewer_id}** {d['decision'].lower()} closure of **{d['ref_id']}** - "
                   f"status is now **{d['status']}**. (Recorded directly: workflow thread not in volatile memory.)")
        else:
            msg = "Decision not recorded:\n\n" + "\n".join(f"- {e.message}" for e in result.errors)
        return TurnResult(thread_id=tid, next_thread_id=tid, response=msg, result=result.to_dict(),
                          errors=[e.to_dict() for e in result.errors], halted=result.halted)

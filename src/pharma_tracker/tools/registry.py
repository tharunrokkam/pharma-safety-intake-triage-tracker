"""Tool registry & executor.

Pipeline for every call:  auto-repair  ->  Pydantic validation  ->  LangChain StructuredTool execution.
Invalid calls (schema errors or domain-rule violations) feed the circuit breaker and are audited
with field names / error codes only.
"""
from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ValidationError

from ..domain import lifecycle
from ..domain.enums import AuditAction, Status
from ..domain.errors import DomainError, FieldError, humanize
from ..domain.schemas import (
    DecideApprovalArgs,
    GetReportArgs,
    IntakeReportIn,
    SearchKnowledgeArgs,
    SubmitIntakeReportArgs,
    UpdateStatusArgs,
)
from ..domain.refgen import REF_PATTERN
from ..persistence.repository import Repository
from .circuit_breaker import HALT_MESSAGE, CircuitBreaker, call_signature
from .repair import repair_args, repair_tool_name

log = logging.getLogger(__name__)
_REF_RE = re.compile(REF_PATTERN)

TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "submit_intake_report": SubmitIntakeReportArgs,
    "update_status": UpdateStatusArgs,
    "get_report": GetReportArgs,
    "search_knowledge": SearchKnowledgeArgs,
    "decide_approval": DecideApprovalArgs,
}

TOOL_DESCRIPTIONS = {
    "submit_intake_report": "Create a new fictional intake report (AE or PQC) and return its reference id.",
    "update_status": "Move a report along New -> In Review -> Closed (Closed requires HITL approval).",
    "get_report": "Fetch a stored report by reference id.",
    "search_knowledge": "Hybrid RAG search over past reports and SOPs (extractive, cited).",
    "decide_approval": "Record a human reviewer's approve/reject decision for a pending closure.",
}


@dataclass
class PreparedCall:
    tool: str
    raw_tool: str
    args: dict[str, Any]
    ok: bool
    repairs: list[str] = field(default_factory=list)
    errors: list[FieldError] = field(default_factory=list)

    @property
    def signature(self) -> str:
        return call_signature(self.tool, self.args)


@dataclass
class ToolResult:
    tool: str
    ok: bool
    data: dict[str, Any] | None = None
    errors: list[FieldError] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)
    halted: bool = False
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "ok": self.ok, "data": self.data, "halted": self.halted,
                "message": self.message, "repairs": list(self.repairs),
                "errors": [e.to_dict() for e in self.errors]}


class ToolExecutor:
    def __init__(
        self,
        repo: Repository,
        search_fn: Callable[[str], dict[str, Any]] | None = None,
        on_report_created: Callable[[str], None] | None = None,
    ):
        self.repo = repo
        self.search_fn = search_fn
        self.on_report_created = on_report_created
        self.tools: dict[str, StructuredTool] = {
            name: StructuredTool.from_function(
                func=getattr(self, f"_h_{name}"), name=name, description=TOOL_DESCRIPTIONS[name],
                args_schema=schema,
            )
            for name, schema in TOOL_SCHEMAS.items()
        }

    # ------------------------------------------------------------------ handlers (run via StructuredTool)
    def _h_submit_intake_report(self, **kw: Any) -> dict[str, Any]:
        actor = kw.pop("actor_id")
        report = IntakeReportIn.model_validate(kw)
        ref_id = self.repo.create_report(report, actor)
        if self.on_report_created:
            self.on_report_created(ref_id)
        return {"ref_id": ref_id, "status": str(Status.NEW)}

    def _h_update_status(self, ref_id: str, target_status: Status, actor_id: str,
                         note: str | None = None) -> dict[str, Any]:
        current = self.repo.require_report(ref_id)["status"]
        lifecycle.validate_transition(current, target_status)
        if lifecycle.requires_hitl(current, target_status):
            approval_id = self.repo.request_closure(ref_id, actor_id)
            return {"ref_id": ref_id, "status": current, "requested_status": str(target_status),
                    "hitl_required": True, "approval_id": approval_id}
        res = self.repo.transition_status(ref_id, target_status, actor_id)
        return {**res, "hitl_required": False}

    def _h_get_report(self, ref_id: str) -> dict[str, Any]:
        return self.repo.require_report(ref_id)

    def _h_search_knowledge(self, query: str) -> dict[str, Any]:
        if self.search_fn is None:
            raise DomainError("Knowledge search is not configured.")
        return self.search_fn(query)

    def _h_decide_approval(self, approval_id: int, reviewer_id: str, decision: str,
                           justification: str) -> dict[str, Any]:
        return self.repo.decide_approval(approval_id, reviewer_id, decision, justification)

    # ------------------------------------------------------------------ pipeline steps
    def prepare(self, tool_name: str, args: dict[str, Any] | None) -> PreparedCall:
        """Auto-repair + strict Pydantic validation. Never raises."""
        known = list(TOOL_SCHEMAS)
        name, name_note = repair_tool_name(tool_name, known)
        repairs = [name_note] if name_note else []
        if name not in TOOL_SCHEMAS:
            return PreparedCall(name, tool_name, dict(args or {}), False, repairs, [FieldError(
                "_tool", "unknown_tool", f"Unknown tool '{tool_name}'. Available tools: {', '.join(known)}.")])
        schema = TOOL_SCHEMAS[name]
        fixed, arg_notes = repair_args(dict(args or {}), set(schema.model_fields))
        repairs += arg_notes
        try:
            parsed = schema.model_validate(fixed)
        except ValidationError as exc:
            return PreparedCall(name, tool_name, fixed, False, repairs, humanize(exc))
        return PreparedCall(name, tool_name, parsed.model_dump(mode="json"), True, repairs)

    def execute(self, prepared: PreparedCall) -> ToolResult:
        """Run a validated call through its LangChain StructuredTool. Domain errors become structured errors."""
        if not prepared.ok:
            return ToolResult(prepared.tool, False, errors=prepared.errors, repairs=prepared.repairs,
                              message="Validation failed.")
        try:
            data = self.tools[prepared.tool].invoke(prepared.args)
        except DomainError as exc:
            return ToolResult(prepared.tool, False, errors=[exc.to_field_error()], repairs=prepared.repairs,
                              message=str(exc))
        except sqlite3.Error as exc:  # e.g. a concurrent write hit a uniqueness constraint
            log.warning("storage error in %s: %s", prepared.tool, type(exc).__name__)
            err = FieldError("_", "storage_error",
                             "The request could not be stored (concurrent update or constraint). Please retry.")
            return ToolResult(prepared.tool, False, errors=[err], repairs=prepared.repairs, message=err.message)
        return ToolResult(prepared.tool, True, data=data, repairs=prepared.repairs, message="OK")

    def register_failure(self, prepared: PreparedCall, errors: list[FieldError], breaker: CircuitBreaker,
                         actor_id: str) -> bool:
        """Audit an invalid call and feed the breaker. Returns True when the breaker trips now."""
        was_open = breaker.is_open
        tripped = breaker.record_failure(prepared.signature)
        raw_ref = prepared.args.get("ref_id")
        ref = raw_ref if isinstance(raw_ref, str) and _REF_RE.match(raw_ref) else None  # never log raw user text
        self.repo.record_event(actor_id, AuditAction.VALIDATION_FAILED, ref_id=ref, details={
            "tool": prepared.tool[:40],
            "fields": sorted({e.field[:40] for e in errors}),
            "codes": sorted({e.code[:40] for e in errors}),
            "consecutive_failures": breaker.consecutive_failures,
        })
        if tripped and not was_open:
            self.repo.record_event(actor_id, AuditAction.CIRCUIT_OPEN, details={
                "tool": prepared.tool[:40],
                "signature_sha256": prepared.signature[:16],
                "consecutive_failures": breaker.consecutive_failures,
                "threshold": breaker.max_failures,
            })
        return tripped

    # ------------------------------------------------------------------ convenience: full call
    def call(self, tool_name: str, args: dict[str, Any] | None, breaker: CircuitBreaker,
             actor_id: str = "SYSTEM") -> ToolResult:
        if breaker.is_open:
            return ToolResult(tool_name, False, halted=True, message=HALT_MESSAGE)
        prepared = self.prepare(tool_name, args)
        result = self.execute(prepared)
        if result.ok:
            breaker.record_success()
            return result
        if self.register_failure(prepared, result.errors, breaker, actor_id):
            result.halted = True
            result.message = HALT_MESSAGE
        return result


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

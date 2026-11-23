"""Deterministic semantic router (control plane step 3) + rule-based argument extraction.

Routing happens before any tool or retrieval call, from an ordered rule table, so the same input
always takes the same path. Each decision carries the rule name and reason for the ReAct trace.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..domain.enums import Status
from ..domain.guards import find_clinical_scope_violation, find_pii


class Route:
    HALTED = "HALTED"
    PII_BLOCKED = "PII_BLOCKED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    GREETING = "GREETING"
    STATUS = "STATUS"
    INTAKE = "INTAKE"
    RAG = "RAG"
    TOOL = "TOOL"  # structured call from a UI form/button

    DIRECT = {HALTED, PII_BLOCKED, OUT_OF_SCOPE, GREETING}


@dataclass(frozen=True)
class RouteDecision:
    route: str
    rule: str
    reason: str
    detail: str = ""


REF_LOOSE = re.compile(r"\bREF[\s_\-#]*\d{4}[\s_\-]*\d{1,4}\b", re.I)
_GREETING = re.compile(r"^\s*(hi|hello|hey|good (morning|afternoon|evening)|help|thanks|thank you|"
                       r"what can you do)\b[\s!.?]*", re.I)
_UPDATE_VERBS = re.compile(r"\b(move|set|change|update|close|start|begin|advance|transition|promote|mark|put)\b",
                           re.I)
_LOOKUP_VERBS = re.compile(r"\b(show|get|view|open|details?|status of|what is the status|lookup|look up|fetch)\b",
                           re.I)
_INTAKE = re.compile(r"\b(new (report|complaint|case|intake)|submit|log (a|an|new)|file (a|an)|create (a|an)? ?report|"
                     r"report an? (adverse|quality|product)|record (a|an) )", re.I)


def route_text(text: str | None) -> RouteDecision:
    """Ordered rules: PII -> clinical scope -> greeting -> status -> intake -> RAG (default)."""
    t = (text or "").strip()
    if not t:
        return RouteDecision(Route.GREETING, "R0_EMPTY", "empty input -> help message")
    pii = find_pii(t)
    if pii:
        return RouteDecision(Route.PII_BLOCKED, "R1_PII", "personal identifiers detected", ", ".join(pii))
    clinical = find_clinical_scope_violation(t)
    if clinical:
        return RouteDecision(Route.OUT_OF_SCOPE, "R2_CLINICAL_SCOPE", f"request for {clinical}", clinical)
    if _GREETING.match(t) and len(t) < 60:
        return RouteDecision(Route.GREETING, "R3_GREETING", "greeting/help phrase")
    has_ref = REF_LOOSE.search(t)
    if has_ref and (_UPDATE_VERBS.search(t) or _LOOKUP_VERBS.search(t)):
        return RouteDecision(Route.STATUS, "R4_STATUS", "reference id + workflow/lookup verb")
    if _INTAKE.search(t):
        return RouteDecision(Route.INTAKE, "R5_INTAKE", "new-submission phrase")
    return RouteDecision(Route.RAG, "R6_DEFAULT_RAG", "knowledge / historical lookup (default)")


# --------------------------------------------------------------------------- argument extraction
_TARGETS = [
    (re.compile(r"\b(close|closed|closure)\b", re.I), Status.CLOSED),
    (re.compile(r"\b(in[\s_\-]?review|start(ing)? review|begin review|review)\b", re.I), Status.IN_REVIEW),
    (re.compile(r"\bto new\b|\bas new\b|\bback to new\b", re.I), Status.NEW),
]


def extract_status_call(text: str, actor_id: str) -> dict[str, Any]:
    """'move REF-2026-0001 to in review' -> update_status(...); 'show REF-...' -> get_report(...)."""
    m = REF_LOOSE.search(text)
    ref = m.group(0) if m else None
    if _UPDATE_VERBS.search(text) and not re.search(r"\bstatus of\b", text, re.I):
        args: dict[str, Any] = {"ref_id": ref, "actor_id": actor_id}
        for pat, status in _TARGETS:
            if pat.search(text):
                args["target_status"] = status.value
                break
        if ref is None:
            args.pop("ref_id")
        return {"tool": "update_status", "args": args}
    return {"tool": "get_report", "args": {"ref_id": ref} if ref else {}}




def extract_intake_call(text: str, actor_id: str) -> dict[str, Any]:
    """Parse 'key=value; key=value' pairs (keys may be aliases - the repair step maps them)."""
    body = text
    segments = [s.strip() for s in re.split(r"[;\n]+", body) if s.strip()]
    args: dict[str, Any] = {}
    for seg in segments:
        if "=" not in seg:
            continue
        key, _, value = seg.partition("=")
        key = key.split(":")[-1].strip()  # drop a leading "new report:" style prefix
        if key:
            args[key] = value.strip()
    args["actor_id"] = actor_id
    return {"tool": "submit_intake_report", "args": args}

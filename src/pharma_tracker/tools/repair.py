"""Deterministic auto-repair of tool calls (control plane step 1).

Repairs are conservative, rule-based and fully reported; anything still invalid afterwards is returned
as a structured validation error by the executor.
"""
from __future__ import annotations

import difflib
import re
from typing import Any

from ..config import TOOL_NAME_FUZZY_CUTOFF
from ..domain.enums import ReporterType, ReportType, Status

KEY_ALIASES: dict[str, str] = {
    "lot": "batch_id", "lot_no": "batch_id", "lot_number": "batch_id", "lotnumber": "batch_id",
    "batch": "batch_id", "batch_no": "batch_id", "batch_number": "batch_id", "batchid": "batch_id",
    "product": "product_name", "productname": "product_name", "drug": "product_name",
    "type": "report_type", "category": "report_type", "reporttype": "report_type",
    "reporter": "reporter_type", "reportertype": "reporter_type", "source": "reporter_type",
    "received": "date_received", "date": "date_received", "received_date": "date_received",
    "desc": "description", "details": "description", "complaint": "description",
    "event": "event_description", "event_desc": "event_description",
    "onset": "event_onset_date", "onset_date": "event_onset_date", "event_onset": "event_onset_date",
    "ref": "ref_id", "reference": "ref_id", "refid": "ref_id", "reference_id": "ref_id",
    "status": "target_status", "new_status": "target_status", "to": "target_status", "target": "target_status",
    "actor": "actor_id", "user": "actor_id", "operator": "actor_id",
    "reviewer": "reviewer_id", "approval": "approval_id", "id": "approval_id",
    "reason": "justification", "q": "query", "question": "query",
}

_STATUS_MAP = {"new": Status.NEW, "inreview": Status.IN_REVIEW, "review": Status.IN_REVIEW,
               "underreview": Status.IN_REVIEW, "closed": Status.CLOSED, "close": Status.CLOSED}
_TYPE_MAP = {
    "ae": ReportType.SUSPECTED_ADVERSE_EVENT, "adverseevent": ReportType.SUSPECTED_ADVERSE_EVENT,
    "suspectedadverseevent": ReportType.SUSPECTED_ADVERSE_EVENT, "sae": ReportType.SUSPECTED_ADVERSE_EVENT,
    "pqc": ReportType.PRODUCT_QUALITY_COMPLAINT, "qualitycomplaint": ReportType.PRODUCT_QUALITY_COMPLAINT,
    "productqualitycomplaint": ReportType.PRODUCT_QUALITY_COMPLAINT,
    "complaint": ReportType.PRODUCT_QUALITY_COMPLAINT, "productcomplaint": ReportType.PRODUCT_QUALITY_COMPLAINT,
}
_REPORTER_MAP = {re.sub(r"[^a-z]", "", r.value.lower()): r for r in ReporterType}
_REPORTER_MAP.update({"hcp": ReporterType.HEALTHCARE_PROFESSIONAL, "doctor": ReporterType.HEALTHCARE_PROFESSIONAL,
                      "nurse": ReporterType.HEALTHCARE_PROFESSIONAL, "patient": ReporterType.CONSUMER,
                      "salesrep": ReporterType.SALES_REPRESENTATIVE})

_LOT_RE = re.compile(r"^\s*lot[\s_\-#:]*(\d{5})\s*$", re.I)
_REF_RE = re.compile(r"^\s*ref[\s_\-#:]*(\d{4})[\s_\-]*(\d{1,4})\s*$", re.I)
_ACTOR_RE = re.compile(r"^\s*(op|rev)[\s_\-]*(\d{1,2})\s*$", re.I)
_DATE_SLASH_RE = re.compile(r"^\s*(\d{4})[/.](\d{1,2})[/.](\d{1,2})\s*$")


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def repair_tool_name(name: str, known: list[str]) -> tuple[str, str | None]:
    if name in known:
        return name, None
    norm = re.sub(r"[\s\-]+", "_", name.strip().lower())
    if norm in known:
        return norm, f"tool name '{name}' normalised to '{norm}'"
    match = difflib.get_close_matches(norm, known, n=1, cutoff=TOOL_NAME_FUZZY_CUTOFF)
    if match:
        return match[0], f"tool name '{name}' auto-corrected to '{match[0]}'"
    return name, None


def _repair_value(key: str, value: Any) -> tuple[Any, str | None]:
    if not isinstance(value, str):
        return value, None
    v = value
    if key == "batch_id":
        m = _LOT_RE.match(v)
        if m and v != f"LOT-{m.group(1)}":
            return f"LOT-{m.group(1)}", f"batch_id normalised to LOT-{m.group(1)}"
    elif key == "ref_id":
        m = _REF_RE.match(v)
        if m:
            fixed = f"REF-{m.group(1)}-{int(m.group(2)):04d}"
            if fixed != v:
                return fixed, f"ref_id normalised to {fixed}"
    elif key in ("actor_id", "reviewer_id"):
        m = _ACTOR_RE.match(v)
        if m:
            fixed = f"{m.group(1).upper()}-{int(m.group(2)):02d}"
            if fixed != v:
                return fixed, f"{key} normalised to {fixed}"
    elif key == "target_status":
        s = _STATUS_MAP.get(_squash(v))
        if s is not None and s.value != v:
            return s.value, f"target_status normalised to '{s.value}'"
    elif key == "report_type":
        t = _TYPE_MAP.get(_squash(v))
        if t is not None and t.value != v:
            return t.value, f"report_type normalised to '{t.value}'"
    elif key == "reporter_type":
        r = _REPORTER_MAP.get(_squash(v))
        if r is not None and r.value != v:
            return r.value, f"reporter_type normalised to '{r.value}'"
    elif key in ("date_received", "event_onset_date"):
        m = _DATE_SLASH_RE.match(v)
        if m:
            fixed = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            return fixed, f"{key} normalised to {fixed}"
    elif key == "decision":
        d = {"approve": "approve", "approved": "approve", "yes": "approve",
             "reject": "reject", "rejected": "reject", "no": "reject"}.get(v.strip().lower())
        if d and d != v:
            return d, f"decision normalised to '{d}'"
    return value, None


def repair_args(args: dict[str, Any], schema_fields: set[str]) -> tuple[dict[str, Any], list[str]]:
    """Map key aliases onto schema fields and normalise well-known value formats."""
    repairs: list[str] = []
    out: dict[str, Any] = {}
    for raw_key, value in (args or {}).items():
        key = str(raw_key).strip()
        norm = re.sub(r"[\s\-]+", "_", key.lower())
        if norm in schema_fields:
            target = norm
        else:
            alias = KEY_ALIASES.get(norm) or KEY_ALIASES.get(norm.replace("_", ""))
            target = alias if alias in schema_fields and alias not in args else key
        if target != key:
            repairs.append(f"argument '{key}' mapped to '{target}'")
        if isinstance(value, str):
            value = value.strip()
        value, note = _repair_value(target, value)
        if note:
            repairs.append(note)
        out[target] = value
    return out, repairs

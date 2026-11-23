"""Typed domain errors and the mapping of Pydantic errors to context-sensitive messages."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from pydantic import ValidationError


@dataclass(frozen=True)
class FieldError:
    field: str
    code: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


class DomainError(Exception):
    code = "domain_error"

    def to_field_error(self, field: str = "_") -> FieldError:
        return FieldError(field=field, code=self.code, message=str(self))


class NotFoundError(DomainError):
    code = "not_found"


class IllegalTransitionError(DomainError):
    code = "illegal_transition"


class ApprovalRequiredError(DomainError):
    code = "approval_required"


class ApprovalStateError(DomainError):
    code = "approval_state"


class SeparationOfDutiesError(DomainError):
    code = "separation_of_duties"


class RefIdOverflowError(DomainError):
    code = "ref_id_overflow"


class AuditPayloadError(DomainError):
    code = "audit_payload"


FIELD_LABELS: dict[str, str] = {
    "report_type": "Report type",
    "product_name": "Product name",
    "batch_id": "Batch/Lot number",
    "date_received": "Date received",
    "reporter_type": "Reporter type",
    "description": "Description",
    "event_description": "Event description",
    "event_onset_date": "Event onset date",
    "actor_id": "Actor ID",
    "ref_id": "Reference ID",
    "target_status": "Target status",
    "note": "Note",
    "query": "Query",
    "approval_id": "Approval ID",
    "reviewer_id": "Reviewer ID",
    "decision": "Decision",
    "justification": "Justification",
}

_FORMAT_HINTS: dict[str, str] = {
    "batch_id": "LOT- followed by exactly 5 digits, e.g. LOT-12345",
    "ref_id": "REF-YYYY-NNNN, e.g. REF-2026-0001",
    "actor_id": "a pseudonymous code such as OP-01 or REV-02",
    "reviewer_id": "a reviewer code such as REV-01",
    "product_name": "letters, digits, spaces and . - / ( ) + only",
}

# Error codes raised by our own validators (domain/schemas.py) - their messages are used verbatim.
CUSTOM_CODES = {"pii_detected", "date_in_future", "ae_field_required", "ae_field_too_short", "not_applicable",
                "onset_after_received"}

# Fields whose raw input may be echoed back in messages (never free text).
_ECHO_SAFE = {"batch_id", "ref_id", "actor_id", "reviewer_id", "target_status", "report_type", "reporter_type"}


def label(field: str) -> str:
    return FIELD_LABELS.get(field, field.replace("_", " ").capitalize())


def _echo(field: str, raw: object) -> str:
    if field in _ECHO_SAFE and isinstance(raw, (str, int)) and len(str(raw)) <= 24:
        return f" (you entered '{raw}')"
    return ""


def humanize_error(err: dict) -> FieldError:
    loc = [str(p) for p in err.get("loc", ()) if not isinstance(p, int)]
    field = loc[0] if loc else "_"
    etype = err.get("type", "value_error")
    ctx = err.get("ctx") or {}
    raw = err.get("input")
    name = label(field)

    if etype in CUSTOM_CODES:
        # PydanticCustomError messages from our validators are already context-specific.
        msg = err.get("msg", f"{name} is invalid.")
    elif etype == "missing":
        msg = f"{name} is required."
    elif etype == "extra_forbidden":
        msg = (f"Field '{field}' is not permitted - the intake must not collect additional "
               "(potentially personal) data.")
    elif etype == "string_pattern_mismatch":
        hint = _FORMAT_HINTS.get(field, f"pattern {ctx.get('pattern', '')}")
        msg = f"{name} must be {hint}{_echo(field, raw)}."
    elif etype == "string_too_short":
        n = len(raw.strip()) if isinstance(raw, str) else 0
        if n == 0:
            msg = f"{name} is required and cannot be blank."
        else:
            msg = f"{name} must be at least {ctx.get('min_length')} characters (currently {n})."
    elif etype == "string_too_long":
        msg = f"{name} must be at most {ctx.get('max_length')} characters."
    elif etype == "enum":
        msg = f"{name} must be one of: {ctx.get('expected', '')}{_echo(field, raw)}."
    elif etype == "literal_error":
        msg = f"{name} must be one of: {ctx.get('expected', '')}."
    elif etype.startswith("date") or etype.startswith("datetime"):
        msg = f"{name} must be a valid calendar date in YYYY-MM-DD format."
    elif etype in ("int_parsing", "int_type", "greater_than"):
        msg = f"{name} must be a positive whole number."
    elif etype == "string_type":
        msg = f"{name} must be text."
    else:
        # PydanticCustomError messages from our validators are already context-specific.
        msg = err.get("msg", f"{name} is invalid.")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
    return FieldError(field=field, code=etype, message=msg)


def humanize(exc: ValidationError) -> list[FieldError]:
    seen: set[tuple[str, str]] = set()
    out: list[FieldError] = []
    for err in exc.errors():
        fe = humanize_error(err)
        if (fe.field, fe.code) not in seen:
            seen.add((fe.field, fe.code))
            out.append(fe)
    return out

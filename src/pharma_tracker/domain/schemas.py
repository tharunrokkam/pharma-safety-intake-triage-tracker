"""Pydantic v2 schemas: intake report + strict tool-argument schemas (control plane step 1)."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from .enums import ReporterType, ReportType, Status
from .guards import find_pii
from .refgen import REF_PATTERN

LOT_PATTERN = r"^LOT-\d{5}$"
ACTOR_PATTERN = r"^(OP|REV)-\d{2}$"
REVIEWER_PATTERN = r"^REV-\d{2}$"
PRODUCT_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 .\-/()+]*$"

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=False)


def _today() -> date:
    return date.today()


def _no_pii(value: Optional[str], field_label: str) -> Optional[str]:
    cats = find_pii(value)
    if cats:
        raise PydanticCustomError(
            "pii_detected",
            "{label} appears to contain personal identifiers ({cats}). Remove them - synthetic data only.",
            {"label": field_label, "cats": ", ".join(cats)},
        )
    return value


class IntakeReportIn(BaseModel):
    """A new intake report. AE extension fields are conditionally mandatory."""

    model_config = _STRICT

    report_type: ReportType
    product_name: str = Field(min_length=2, max_length=100, pattern=PRODUCT_PATTERN)
    batch_id: str = Field(pattern=LOT_PATTERN)
    date_received: date
    reporter_type: ReporterType
    description: str = Field(min_length=20, max_length=2000)
    event_description: Optional[str] = Field(default=None, max_length=2000, validate_default=True)
    event_onset_date: Optional[date] = Field(default=None, validate_default=True)

    @field_validator("date_received")
    @classmethod
    def _received_not_future(cls, v: date) -> date:
        if v > _today():
            raise PydanticCustomError("date_in_future", "Date received cannot be in the future.")
        return v

    @field_validator("description")
    @classmethod
    def _description_clean(cls, v: str) -> str:
        return _no_pii(v, "Description")  # type: ignore[return-value]

    @field_validator("event_description")
    @classmethod
    def _event_description_rule(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        rtype = info.data.get("report_type")
        if v is not None and v == "":
            v = None
        if rtype == ReportType.SUSPECTED_ADVERSE_EVENT:
            if v is None:
                raise PydanticCustomError(
                    "ae_field_required",
                    "Event description is required for Suspected Adverse Event reports "
                    "(describe what was observed - no patient identifiers).",
                )
            if len(v) < 10:
                raise PydanticCustomError(
                    "ae_field_too_short", "Event description must be at least 10 characters."
                )
            return _no_pii(v, "Event description")
        if rtype == ReportType.PRODUCT_QUALITY_COMPLAINT and v is not None:
            raise PydanticCustomError(
                "not_applicable",
                "Event description only applies to Suspected Adverse Event reports - leave it empty "
                "for Product Quality Complaints.",
            )
        return v

    @field_validator("event_onset_date")
    @classmethod
    def _onset_rule(cls, v: Optional[date], info: ValidationInfo) -> Optional[date]:
        rtype = info.data.get("report_type")
        if rtype == ReportType.SUSPECTED_ADVERSE_EVENT:
            if v is None:
                raise PydanticCustomError(
                    "ae_field_required",
                    "Event onset date is required for Suspected Adverse Event reports.",
                )
            if v > _today():
                raise PydanticCustomError("date_in_future", "Event onset date cannot be in the future.")
            received = info.data.get("date_received")
            if received is not None and v > received:
                raise PydanticCustomError(
                    "onset_after_received",
                    "Event onset date ({onset}) cannot be after the date the report was received ({received}).",
                    {"onset": v.isoformat(), "received": received.isoformat()},
                )
            return v
        if rtype == ReportType.PRODUCT_QUALITY_COMPLAINT and v is not None:
            raise PydanticCustomError(
                "not_applicable",
                "Event onset date only applies to Suspected Adverse Event reports - leave it empty "
                "for Product Quality Complaints.",
            )
        return v


# --------------------------------------------------------------------------- tool argument schemas
class SubmitIntakeReportArgs(IntakeReportIn):
    actor_id: str = Field(pattern=ACTOR_PATTERN)


class UpdateStatusArgs(BaseModel):
    model_config = _STRICT

    ref_id: str = Field(pattern=REF_PATTERN)
    target_status: Status
    actor_id: str = Field(pattern=ACTOR_PATTERN)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def _note_clean(cls, v: Optional[str]) -> Optional[str]:
        return _no_pii(v, "Note")


class GetReportArgs(BaseModel):
    model_config = _STRICT

    ref_id: str = Field(pattern=REF_PATTERN)


class SearchKnowledgeArgs(BaseModel):
    model_config = _STRICT

    query: str = Field(min_length=3, max_length=500)


class DecideApprovalArgs(BaseModel):
    model_config = _STRICT

    approval_id: int = Field(gt=0)
    reviewer_id: str = Field(pattern=REVIEWER_PATTERN)
    decision: Literal["approve", "reject"]
    justification: str = Field(min_length=10, max_length=500)

    @field_validator("justification")
    @classmethod
    def _justification_clean(cls, v: str) -> str:
        return _no_pii(v, "Justification")  # type: ignore[return-value]

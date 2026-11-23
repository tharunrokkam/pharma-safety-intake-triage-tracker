"""Schema validation: mandatory fields, regex formats, conditional AE rules, PII shield, extra keys."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from pharma_tracker.domain.errors import humanize
from pharma_tracker.domain.schemas import DecideApprovalArgs, IntakeReportIn, UpdateStatusArgs


def errors_for(data: dict) -> dict[str, str]:
    with pytest.raises(ValidationError) as ei:
        IntakeReportIn.model_validate(data)
    return {e.field: e.message for e in humanize(ei.value)}


def test_valid_ae_and_pqc(ae_fields, pqc_fields):
    ae = IntakeReportIn.model_validate(ae_fields)
    pqc = IntakeReportIn.model_validate(pqc_fields)
    assert ae.event_onset_date == date(2026, 11, 19)
    assert pqc.event_description is None


@pytest.mark.parametrize("field", ["report_type", "product_name", "batch_id", "date_received",
                                   "reporter_type", "description"])
def test_each_core_field_is_mandatory(pqc_fields, field):
    data = dict(pqc_fields)
    data.pop(field)
    errs = errors_for(data)
    assert field in errs and "required" in errs[field].lower()


@pytest.mark.parametrize("field", ["event_description", "event_onset_date"])
def test_ae_extension_required_for_ae(ae_fields, field):
    data = dict(ae_fields)
    data.pop(field)
    errs = errors_for(data)
    assert "Suspected Adverse Event" in errs[field]


def test_ae_fields_rejected_for_pqc(pqc_fields):
    errs = errors_for({**pqc_fields, "event_description": "Something happened here", "event_onset_date": "2026-11-01"})
    assert "only applies" in errs["event_description"]
    assert "only applies" in errs["event_onset_date"]


@pytest.mark.parametrize("lot", ["LOT-1234", "LOT-123456", "lot88392", "LOT88392", "88392", "LOT-ABCDE"])
def test_bad_lot_formats(pqc_fields, lot):
    errs = errors_for({**pqc_fields, "batch_id": lot})
    assert "LOT- followed by exactly 5 digits" in errs["batch_id"]


def test_future_dates_rejected(ae_fields):
    future = (date.today() + timedelta(days=3)).isoformat()
    errs = errors_for({**ae_fields, "date_received": future})
    assert "future" in errs["date_received"]
    errs = errors_for({**ae_fields, "event_onset_date": future})
    assert "future" in errs["event_onset_date"]


def test_onset_after_received_rejected(ae_fields):
    errs = errors_for({**ae_fields, "event_onset_date": "2026-11-20", "date_received": "2026-11-18"})
    assert "cannot be after" in errs["event_onset_date"]


def test_description_min_length_message(pqc_fields):
    errs = errors_for({**pqc_fields, "description": "too short"})
    assert "at least 20 characters (currently 9)" in errs["description"]


def test_blank_description_is_required(pqc_fields):
    errs = errors_for({**pqc_fields, "description": "   "})
    assert "required" in errs["description"]


def test_extra_keys_forbidden(pqc_fields):
    errs = errors_for({**pqc_fields, "patient_name": "anyone"})
    assert "not permitted" in errs["patient_name"]


@pytest.mark.parametrize("text", [
    "Reporter can be reached at someone@example.com for follow up.",
    "Call back on +1 555 123 4567 regarding the tablets please.",
    "Patient name recorded in notes, tablets were cracked badly.",
    "Mr. Smith said the tablets were cracked and discoloured.",
    "Date of birth 1980-01-01, complaint about cracked tablets.",
])
def test_pii_rejected_in_description(pqc_fields, text):
    errs = errors_for({**pqc_fields, "description": text})
    assert "personal identifiers" in errs["description"]


def test_pii_message_does_not_echo_text(pqc_fields):
    errs = errors_for({**pqc_fields, "description": "Contact someone@example.com about cracked tablets."})
    assert "someone@example.com" not in errs["description"]


def test_invalid_enum_message(pqc_fields):
    errs = errors_for({**pqc_fields, "reporter_type": "Neighbour"})
    assert "must be one of" in errs["reporter_type"]


def test_update_status_args_regex():
    UpdateStatusArgs(ref_id="REF-2026-0001", target_status="In Review", actor_id="OP-01")
    with pytest.raises(ValidationError):
        UpdateStatusArgs(ref_id="REF-26-1", target_status="In Review", actor_id="OP-01")
    with pytest.raises(ValidationError):
        UpdateStatusArgs(ref_id="REF-2026-0001", target_status="Archived", actor_id="OP-01")
    with pytest.raises(ValidationError):
        UpdateStatusArgs(ref_id="REF-2026-0001", target_status="In Review", actor_id="John")


def test_decide_approval_requires_reviewer_code_and_justification():
    DecideApprovalArgs(approval_id=1, reviewer_id="REV-01", decision="approve", justification="All checks complete.")
    with pytest.raises(ValidationError):
        DecideApprovalArgs(approval_id=1, reviewer_id="OP-01", decision="approve", justification="All checks complete.")
    with pytest.raises(ValidationError):
        DecideApprovalArgs(approval_id=1, reviewer_id="REV-01", decision="approve", justification="ok")

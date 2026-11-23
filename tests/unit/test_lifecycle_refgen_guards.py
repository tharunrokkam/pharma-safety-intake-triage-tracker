"""Lifecycle rules, reference-id format and the deterministic guards."""
from __future__ import annotations

import pytest

from pharma_tracker.domain.enums import Status
from pharma_tracker.domain.errors import IllegalTransitionError, RefIdOverflowError
from pharma_tracker.domain.guards import find_clinical_scope_violation, find_pii
from pharma_tracker.domain.lifecycle import allowed_targets, requires_hitl, validate_transition
from pharma_tracker.domain.refgen import format_ref, parse_ref


@pytest.mark.parametrize("cur,tgt", [(Status.NEW, Status.IN_REVIEW), (Status.IN_REVIEW, Status.CLOSED)])
def test_legal_transitions(cur, tgt):
    validate_transition(cur, tgt)


@pytest.mark.parametrize("cur,tgt", [
    (Status.NEW, Status.CLOSED), (Status.IN_REVIEW, Status.NEW), (Status.CLOSED, Status.NEW),
    (Status.CLOSED, Status.IN_REVIEW), (Status.NEW, Status.NEW), (Status.CLOSED, Status.CLOSED),
])
def test_illegal_transitions(cur, tgt):
    with pytest.raises(IllegalTransitionError):
        validate_transition(cur, tgt)


def test_only_close_requires_hitl():
    assert requires_hitl(Status.IN_REVIEW, Status.CLOSED)
    assert not requires_hitl(Status.NEW, Status.IN_REVIEW)


def test_allowed_targets():
    assert allowed_targets("New") == [Status.IN_REVIEW]
    assert allowed_targets("Closed") == []


def test_ref_format_and_overflow():
    assert format_ref(2026, 1) == "REF-2026-0001"
    assert parse_ref("REF-2026-0042") == (2026, 42)
    with pytest.raises(RefIdOverflowError):
        format_ref(2026, 10000)


def test_pii_clean_text_and_ids_not_flagged():
    assert find_pii("Cracked tablets in LOT-88392, received 2026-11-20, ref REF-2026-0001.") == []


def test_pii_categories():
    assert "email address" in find_pii("mail a@b.co")
    assert "phone number" in find_pii("ring 020 7946 0958 now")


@pytest.mark.parametrize("text", [
    "Was the rash caused by Fictivex?", "Is this event related to the drug?",
    "What dose should be given?", "Should the patient stop taking it?",
    "Is this case reportable to the FDA?", "recommend a treatment",
])
def test_clinical_requests_detected(text):
    assert find_clinical_scope_violation(text)


@pytest.mark.parametrize("text", [
    "any history of difficulty breathing with LOT-88392?", "what does the SOP say about closing a report?",
    "cracked tablets complaints",
])
def test_normal_queries_not_flagged(text):
    assert find_clinical_scope_violation(text) is None

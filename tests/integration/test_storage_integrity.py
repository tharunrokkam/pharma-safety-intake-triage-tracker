"""Repository + audit trail integrity: ref ids, round-trips, append-only triggers, hash chain, minimisation."""
from __future__ import annotations

import json
import sqlite3
import threading

import pytest

from pharma_tracker.domain.enums import Status
from pharma_tracker.domain.errors import (
    ApprovalRequiredError,
    ApprovalStateError,
    AuditPayloadError,
    IllegalTransitionError,
    RefIdOverflowError,
    SeparationOfDutiesError,
)
from pharma_tracker.domain.schemas import IntakeReportIn


def test_sequential_unique_refs(make_report):
    refs = [make_report("ae"), make_report("pqc"), make_report("ae")]
    year = refs[0][4:8]
    assert refs == [f"REF-{year}-0001", f"REF-{year}-0002", f"REF-{year}-0003"]


def test_concurrent_ref_generation_is_unique(repo, pqc_fields):
    report = IntakeReportIn.model_validate(pqc_fields)
    out: list[str] = []
    lock = threading.Lock()

    def worker():
        for _ in range(5):
            ref = repo.create_report(report, "OP-01")
            with lock:
                out.append(ref)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(out) == 20 and len(set(out)) == 20


def test_ref_overflow(repo, pqc_fields):
    conn = sqlite3.connect(repo.db_path)
    conn.execute("INSERT INTO ref_counters(year, last_seq) VALUES (2026, 9999)")
    conn.commit()
    conn.close()
    with pytest.raises(RefIdOverflowError):
        repo.create_report(IntakeReportIn.model_validate(pqc_fields), "OP-01", year=2026)
    assert repo.list_reports() == []  # rolled back


def test_round_trip_ae(repo, make_report, ae_fields):
    ref = make_report("ae")
    rep = repo.get_report(ref)
    assert rep["status"] == "New" and rep["batch_id"] == ae_fields["batch_id"]
    assert rep["event_onset_date"] == ae_fields["event_onset_date"]
    assert repo.list_transitions(ref)[0]["to_status"] == "New"


def test_filters(repo, make_report):
    a, p = make_report("ae"), make_report("pqc")
    repo.transition_status(p, Status.IN_REVIEW, "OP-01")
    assert [r["ref_id"] for r in repo.list_reports(statuses=["In Review"])] == [p]
    assert [r["ref_id"] for r in repo.list_reports(report_types=["Suspected Adverse Event"])] == [a]
    assert repo.list_reports(statuses=["Closed"], report_types=["Product Quality Complaint"]) == []


def test_audit_log_is_append_only(repo, make_report):
    make_report("ae")
    conn = sqlite3.connect(repo.db_path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE audit_log SET actor_id = 'X'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM audit_log")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM status_transitions")
    conn.close()


def test_hash_chain_verifies_and_detects_tamper(repo, make_report):
    ref = make_report("ae")
    repo.transition_status(ref, Status.IN_REVIEW, "OP-01")
    assert repo.verify_audit_chain().ok
    conn = sqlite3.connect(repo.db_path)
    conn.execute("DROP TRIGGER trg_audit_no_update")  # simulate an attacker with raw DB access
    conn.execute("UPDATE audit_log SET actor_id = 'OP-99' WHERE id = 1")
    conn.commit()
    conn.close()
    report = repo.verify_audit_chain()
    assert not report.ok and report.first_bad_id == 1


def test_audit_contains_no_free_text(repo, make_report, ae_fields):
    ref = make_report("ae")
    repo.transition_status(ref, Status.IN_REVIEW, "OP-01")
    dump = json.dumps(repo.list_audit())
    for field in ("description", "event_description"):
        assert ae_fields[field] not in dump
    created = [a for a in repo.list_audit() if a["action"] == "REPORT_CREATED"][0]
    assert "event_description" in json.loads(created["details_json"])["fields_captured"]  # names only


def test_audit_refuses_free_text_payload(repo):
    with pytest.raises(AuditPayloadError):
        repo.record_event("OP-01", "VALIDATION_FAILED", details={"text": "x" * 200})


def test_illegal_transition_and_close_without_approval(repo, make_report):
    ref = make_report("pqc")
    with pytest.raises(IllegalTransitionError):
        repo.transition_status(ref, Status.CLOSED, "OP-01")
    repo.transition_status(ref, Status.IN_REVIEW, "OP-01")
    with pytest.raises(ApprovalRequiredError):
        repo.transition_status(ref, Status.CLOSED, "OP-01")
    assert repo.get_report(ref)["status"] == "In Review"


def test_approval_flow_and_separation_of_duties(repo, make_report):
    ref = make_report("pqc")
    repo.transition_status(ref, Status.IN_REVIEW, "OP-01")
    ap = repo.request_closure(ref, "REV-01")
    with pytest.raises(ApprovalStateError):
        repo.request_closure(ref, "REV-01")  # only one pending request
    with pytest.raises(SeparationOfDutiesError):
        repo.decide_approval(ap, "REV-01", "approve", "Self approval must fail.")
    assert repo.get_approval(ap)["status"] == "PENDING"
    res = repo.decide_approval(ap, "REV-02", "approve", "All closure checks complete.")
    assert res["status"] == "Closed" and repo.get_approval(ap)["status"] == "APPROVED"
    with pytest.raises(ApprovalStateError):
        repo.decide_approval(ap, "REV-02", "approve", "Second decision must fail.")
    actions = [a["action"] for a in reversed(repo.list_audit(ref_id=ref))]
    assert actions == ["REPORT_CREATED", "STATUS_CHANGED", "APPROVAL_REQUESTED", "APPROVAL_GRANTED", "STATUS_CHANGED"]
    assert repo.verify_audit_chain().ok


def test_rejected_closure_stays_in_review(repo, make_report):
    ref = make_report("pqc")
    repo.transition_status(ref, Status.IN_REVIEW, "OP-01")
    ap = repo.request_closure(ref, "OP-01")
    res = repo.decide_approval(ap, "REV-01", "reject", "Batch register check missing.")
    assert res["status"] == "In Review" and res["decision"] == "REJECTED"
    assert repo.request_closure(ref, "OP-01") > ap  # may re-request after rejection

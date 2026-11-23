"""Regression tests for findings from the pharma-intake-review checklist pass (docs/reviews/)."""
from __future__ import annotations

import sqlite3

from pharma_tracker.tools.circuit_breaker import CircuitBreaker
from pharma_tracker.tools.registry import ToolExecutor


def test_invalid_ref_text_never_reaches_audit(repo):
    ex = ToolExecutor(repo)
    ex.call("update_status", {"ref_id": "a@b.co", "target_status": "In Review", "actor_id": "OP-01"},
            CircuitBreaker(), "OP-01")
    rows = repo.list_audit(actions=["VALIDATION_FAILED"])
    assert rows and all(r["ref_id"] is None for r in rows)
    assert "a@b.co" not in str(rows)


def test_storage_errors_become_structured_errors(repo, make_report, monkeypatch):
    ref = make_report("pqc")
    ex = ToolExecutor(repo)

    def boom(*a, **k):
        raise sqlite3.IntegrityError("UNIQUE constraint failed")

    monkeypatch.setattr(repo, "transition_status", boom)
    res = ex.call("update_status", {"ref_id": ref, "target_status": "In Review", "actor_id": "OP-01"},
                  CircuitBreaker(), "OP-01")
    assert not res.ok and res.errors[0].code == "storage_error"


def test_pii_in_status_note_rejected(repo, make_report):
    ref = make_report("pqc")
    res = ToolExecutor(repo).call("update_status", {"ref_id": ref, "target_status": "In Review", "actor_id": "OP-01",
                                                    "note": "call back on 020 7946 0958"}, CircuitBreaker(), "OP-01")
    assert not res.ok and res.errors[0].field == "note" and "personal identifiers" in res.errors[0].message
    assert repo.get_report(ref)["status"] == "New"

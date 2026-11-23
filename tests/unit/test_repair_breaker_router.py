"""Auto-repair, circuit breaker boundaries and the deterministic router."""
from __future__ import annotations

import pytest

from pharma_tracker.agent.router import Route, extract_intake_call, extract_status_call, route_text
from pharma_tracker.tools.circuit_breaker import CircuitBreaker, call_signature
from pharma_tracker.tools.registry import TOOL_SCHEMAS
from pharma_tracker.tools.repair import repair_args, repair_tool_name

KNOWN = list(TOOL_SCHEMAS)


# ---------------------------------------------------------------- repair
@pytest.mark.parametrize("typo,expected", [
    ("submit_intake_reprot", "submit_intake_report"), ("Update Status", "update_status"),
    ("update-status", "update_status"), ("updat_status", "update_status"),
])
def test_tool_name_repair(typo, expected):
    assert repair_tool_name(typo, KNOWN)[0] == expected


def test_unrelated_tool_name_not_repaired():
    assert repair_tool_name("delete_everything", KNOWN)[0] == "delete_everything"


def test_key_aliases_and_value_normalisation():
    fields = set(TOOL_SCHEMAS["submit_intake_report"].model_fields)
    out, notes = repair_args({"lot": "lot 88392", "type": "AE", "reporter": "hcp", "received": "2026/11/2",
                              "actor": "op1"}, fields)
    assert out["batch_id"] == "LOT-88392"
    assert out["report_type"] == "Suspected Adverse Event"
    assert out["reporter_type"] == "Healthcare Professional"
    assert out["date_received"] == "2026-11-02"
    assert out["actor_id"] == "OP-01"
    assert any("mapped to 'batch_id'" in n for n in notes)


def test_status_and_ref_normalisation():
    fields = set(TOOL_SCHEMAS["update_status"].model_fields)
    out, _ = repair_args({"ref": "ref 2026 1", "status": "in_review", "actor_id": "OP-01"}, fields)
    assert out == {"ref_id": "REF-2026-0001", "target_status": "In Review", "actor_id": "OP-01"}


def test_wrong_digit_lot_is_not_repaired():
    out, _ = repair_args({"batch_id": "lot 1234"}, {"batch_id"})
    assert out["batch_id"] == "lot 1234"


# ---------------------------------------------------------------- circuit breaker
def test_breaker_trips_on_third_identical_failure():
    b = CircuitBreaker(max_failures=2)
    sig = call_signature("update_status", {"ref_id": "X"})
    assert b.record_failure(sig) is False
    assert b.record_failure(sig) is False
    assert b.record_failure(sig) is True
    assert b.is_open


def test_breaker_resets_on_success():
    b = CircuitBreaker()
    sig = call_signature("t", {"a": 1})
    b.record_failure(sig)
    b.record_failure(sig)
    b.record_success()
    assert b.record_failure(sig) is False
    assert b.consecutive_failures == 1


def test_breaker_resets_on_different_signature():
    b = CircuitBreaker()
    s1, s2 = call_signature("t", {"a": 1}), call_signature("t", {"a": 2})
    b.record_failure(s1)
    b.record_failure(s1)
    assert b.record_failure(s2) is False
    assert b.consecutive_failures == 1


def test_signature_is_order_independent():
    assert call_signature("t", {"a": 1, "b": 2}) == call_signature("t", {"b": 2, "a": 1})


def test_breaker_roundtrip_dict():
    b = CircuitBreaker()
    b.record_failure("x")
    assert CircuitBreaker.from_dict(b.to_dict()) == b


# ---------------------------------------------------------------- router
@pytest.mark.parametrize("text,route", [
    ("", Route.GREETING),
    ("hello", Route.GREETING),
    ("help", Route.GREETING),
    ("Was the dyspnea caused by Fictivex?", Route.OUT_OF_SCOPE),
    ("should the patient stop taking Fictivex?", Route.OUT_OF_SCOPE),
    ("is REF-2026-0001 reportable to the FDA?", Route.OUT_OF_SCOPE),
    ("contact me at someone@example.com", Route.PII_BLOCKED),
    ("move REF-2026-0001 to in review", Route.STATUS),
    ("close REF-2026-0003", Route.STATUS),
    ("show REF-2026-0001", Route.STATUS),
    ("new report: type=PQC; product=Placebrix 5mg", Route.INTAKE),
    ("I want to log a new complaint", Route.INTAKE),
    ("any history of difficulty breathing with LOT-88392?", Route.RAG),
    ("what does the SOP say about closing a report?", Route.RAG),
])
def test_router_table(text, route):
    assert route_text(text).route == route


def test_router_is_deterministic():
    assert all(route_text("close REF-2026-0001") == route_text("close REF-2026-0001") for _ in range(5))


def test_extract_status_call():
    c = extract_status_call("please move REF-2026-0001 to in review", "OP-01")
    assert c == {"tool": "update_status", "args": {"ref_id": "REF-2026-0001", "actor_id": "OP-01",
                                                   "target_status": "In Review"}}
    assert extract_status_call("close REF-2026-0002", "OP-01")["args"]["target_status"] == "Closed"
    assert extract_status_call("show REF-2026-0002", "OP-01") == {"tool": "get_report",
                                                                 "args": {"ref_id": "REF-2026-0002"}}


def test_extract_intake_call():
    c = extract_intake_call("new report: type=PQC; product=Placebrix 5mg; lot=LOT-10457; "
                            "event description=none", "OP-02")
    assert c["tool"] == "submit_intake_report"
    assert c["args"]["type"] == "PQC" and c["args"]["lot"] == "LOT-10457"
    assert c["args"]["event description"] == "none" and c["args"]["actor_id"] == "OP-02"

"""LangGraph control plane: routing, tool validation/repair, HITL interrupt/resume, circuit breaker halt."""
from __future__ import annotations

from pharma_tracker.agent.router import Route


def _seed_in_review(service, fields) -> str:
    res = service.submit_report("seed", fields, "OP-01")
    ref = res.result["data"]["ref_id"]
    assert service.update_status("seed", ref, "In Review", "OP-01").ok
    return ref


def test_form_submit_through_graph_with_repairs(service, ae_fields):
    res = service.submit_report("t1", {**ae_fields, "batch_id": "lot-88392", "reporter_type": "hcp"}, "OP-01")
    assert res.ok and res.route == Route.TOOL
    assert res.result["data"]["ref_id"].startswith("REF-")
    assert any("LOT-88392" in r for r in res.result["repairs"])
    actions = [t["action"] for t in res.trace]
    assert actions[0].startswith("pass") and any(a.startswith("validate(") for a in actions)


def test_form_validation_errors_are_structured(service, ae_fields):
    bad = {k: v for k, v in ae_fields.items() if k != "event_onset_date"}
    res = service.submit_report("t1", {**bad, "batch_id": "LOT-12"}, "OP-01")
    assert not res.ok and not res.halted
    fields = {e["field"] for e in res.errors}
    assert {"batch_id", "event_onset_date"} <= fields
    assert service.repo.list_reports() == []
    assert service.repo.list_audit(actions=["VALIDATION_FAILED"])


def test_chat_intake_key_values(service):
    res = service.chat("t1", "new report: type=PQC; product=Placebrix 5mg; lot=lot 10457; received=2026-11-21; "
                             "reporter=Pharmacist; description=Discoloured tablets found in a sealed bottle.", "OP-02")
    assert res.route == Route.INTAKE and res.ok, res.response
    assert service.repo.get_report(res.result["data"]["ref_id"])["batch_id"] == "LOT-10457"


def test_status_chat_and_hitl_interrupt_resume(service, pqc_fields):
    ref = _seed_in_review(service, pqc_fields)
    res = service.chat("chat-1", f"close {ref}", "OP-01")
    assert res.route == Route.STATUS and res.interrupted
    assert res.interrupt_payload["ref_id"] == ref and res.next_thread_id != "chat-1"
    # state frozen: still In Review, approval pending, LangGraph thread paused at hitl_gate
    assert service.repo.get_report(ref)["status"] == "In Review"
    ap = service.repo.list_approvals("PENDING")[0]
    assert ap["thread_id"] == "chat-1" and service.has_live_interrupt("chat-1")
    # invalid decision (separation of duties) keeps the gate armed
    bad = service.decide_approval(ap["id"], "REV-01", "approve", "x")  # too-short justification
    assert bad.interrupted and service.repo.get_report(ref)["status"] == "In Review"
    good = service.decide_approval(ap["id"], "REV-02", "approve", "All closure checks complete.")
    assert not good.interrupted and "Closed" in good.response
    assert service.repo.get_report(ref)["status"] == "Closed"
    assert not service.has_live_interrupt("chat-1")
    assert service.repo.verify_audit_chain().ok


def test_requester_cannot_self_approve_via_graph(service, pqc_fields):
    ref = _seed_in_review(service, pqc_fields)
    res = service.update_status("ui-1", ref, "Closed", "REV-01")
    assert res.interrupted
    ap = service.repo.list_approvals("PENDING")[0]
    r = service.decide_approval(ap["id"], "REV-01", "approve", "Trying to approve my own request.")
    assert r.interrupted and "Separation of duties" in r.response
    r = service.decide_approval(ap["id"], "REV-02", "reject", "Hand-off evidence not attached.")
    assert service.repo.get_report(ref)["status"] == "In Review"
    assert service.repo.get_approval(ap["id"])["status"] == "REJECTED"


def test_decision_after_restart_without_live_thread(service, pqc_fields):
    ref = _seed_in_review(service, pqc_fields)
    ap_id = service.repo.request_closure(ref, "OP-01", thread_id="lost-thread")
    res = service.decide_approval(ap_id, "REV-01", "approve", "Decided after a restart.")
    assert service.repo.get_report(ref)["status"] == "Closed" and "directly" in res.response


def test_illegal_transition_via_chat(service, pqc_fields):
    ref = service.submit_report("t", pqc_fields, "OP-01").result["data"]["ref_id"]
    res = service.chat("t", f"close {ref}", "OP-01")
    assert not res.interrupted and "Illegal transition" in res.response
    assert service.repo.get_report(ref)["status"] == "New"


def test_circuit_breaker_halts_graph(service):
    responses = [service.chat("cb", "move REF-2026-0999 to in review", "OP-01") for _ in range(3)]
    assert [r.halted for r in responses] == [False, False, True]
    assert responses[1].breaker["consecutive_failures"] == 2
    # once open, even a valid request is refused for this thread
    again = service.chat("cb", "hello", "OP-01")
    assert again.halted and again.route == Route.HALTED
    assert len(service.repo.list_audit(actions=["CIRCUIT_OPEN"])) == 1
    # a fresh thread (session reset) works
    assert service.chat("cb-2", "hello", "OP-01").route == Route.GREETING


def test_varied_invalid_calls_do_not_trip(service):
    for i in range(5):
        r = service.chat("cb3", f"move REF-2026-09{i:02d} to in review", "OP-01")
        assert not r.halted


def test_out_of_scope_and_pii_refusals_are_audited(service):
    r = service.chat("g", "Was the rash caused by Fictivex?", "OP-01")
    assert r.route == Route.OUT_OF_SCOPE and "never assesses causality" in r.response
    r = service.chat("g", "email the reporter at someone@example.com", "OP-01")
    assert r.route == Route.PII_BLOCKED and "someone@example.com" not in r.response
    refused = service.repo.list_audit(actions=["REQUEST_REFUSED"])
    assert len(refused) == 2 and "someone@example.com" not in str(refused)


def test_rag_route_returns_cited_answer(service, ae_fields):
    service.submit_report("t", ae_fields, "OP-01")
    r = service.chat("rag", "difficulty breathing LOT-88392", "OP-01")
    assert r.route == Route.RAG and r.retrieval and not r.retrieval["abstained"]
    assert any(c.startswith("REF-") for c in r.retrieval["citations"])
    assert [t["action"] for t in r.trace][-1] == "extractive_composer"
    assert service.repo.list_audit(actions=["RAG_QUERY"])

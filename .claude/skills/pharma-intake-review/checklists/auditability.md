# Checklist — Auditability

- [ ] Every create / status change / approval request / approval decision / validation failure /
      circuit-breaker trip writes exactly one `audit_log` row in the same transaction as the change.
- [ ] Audit rows carry: UTC timestamp, actor_id, action, ref_id, from_status, to_status, details_json,
      prev_hash, row_hash.
- [ ] `audit_log` has `BEFORE UPDATE` and `BEFORE DELETE` triggers that `RAISE(ABORT)`.
- [ ] `row_hash = sha256(prev_hash + canonical payload)`; `verify_chain()` detects tampering and is
      exposed via `scripts/verify_audit_chain.py` and the Audit Trail page.
- [ ] `status_transitions` mirrors every lifecycle change (from, to, actor, ts, approval_id when closing).
- [ ] HITL: approval row PENDING -> APPROVED/REJECTED with reviewer_id + justification recorded;
      reviewer != requester; pending approvals survive restart (read from DB).
- [ ] Timestamps are UTC ISO-8601; no local-time ambiguity.
- [ ] The governance hook is registered in `.claude/settings.json` and writes deterministic JSONL.

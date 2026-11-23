# Checklist — Test Coverage

- [ ] Schema: valid AE + valid PQC; each missing mandatory field; bad lot formats; future dates;
      onset after received; AE fields missing for AE; extra keys rejected; PII strings rejected.
- [ ] Ref-id: sequential, unique, per-year, format, overflow.
- [ ] Storage: report round-trip; audit UPDATE/DELETE blocked; hash chain verifies and detects tamper;
      no free text in audit rows.
- [ ] Lifecycle: all legal transitions; every illegal transition; close without approval refused;
      reviewer == requester refused.
- [ ] HITL graph: close request interrupts (status stays In Review); approve resumes -> Closed;
      reject -> In Review.
- [ ] Circuit breaker: 2 invalid ok, 3rd trips; reset on success; reset on new signature; graph halts.
- [ ] Router: table-driven cases for every rule incl. clinical refusals.
- [ ] Repair: tool-name typo, key aliases, lot/status normalisation.
- [ ] RAG: tokenizer keeps LOT/REF ids whole; BM25 params applied; RRF math (k=60) hand-checked;
      threshold + top-5 cap; abstain; end-to-end pipeline with fakes; real-model tests `@pytest.mark.models`.
- [ ] Tests use `tmp_path` DBs only and never the real `data/db/`.
- [ ] `pytest -q` green; coverage report reviewed for untested branches in domain/tools/agent.

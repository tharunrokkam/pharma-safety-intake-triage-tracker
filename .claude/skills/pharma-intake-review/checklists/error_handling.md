# Checklist — Error Handling & Validation

- [ ] Every mandatory field has a context-sensitive message in `domain/errors.py` (names the field, the
      expected format, and — for AE-only fields — why it is required for this report type).
- [ ] Conditional rules: AE requires event_description + event_onset_date; onset <= date_received;
      no future dates; PQC ignores/rejects AE fields consistently.
- [ ] Regex formats enforced: `^LOT-\d{5}$`, `^REF-\d{4}-\d{4}$`, `^(OP|REV)-\d{2}$`.
- [ ] Tool calls: auto-repair is deterministic and every repair is recorded in the ReAct trace; if repair
      fails a structured `ToolValidationError` (tool, field, code, message) is returned, not raised raw.
- [ ] Circuit breaker opens on the 3rd consecutive identical invalid call (> 2), resets on success or a
      different signature, and halts the graph with a clear user message.
- [ ] Illegal lifecycle transitions raise `IllegalTransitionError`; UI only offers legal transitions.
- [ ] No bare `except:`; exceptions are typed; DB operations use transactions and roll back on failure.
- [ ] Ref-id generation is atomic (`BEGIN IMMEDIATE`) and overflow beyond 9999 raises explicitly.
- [ ] RAG: empty corpus / nothing above threshold -> explicit abstain message, never a fabricated answer.
- [ ] Out-of-scope clinical questions -> fixed refusal, no partial answer.

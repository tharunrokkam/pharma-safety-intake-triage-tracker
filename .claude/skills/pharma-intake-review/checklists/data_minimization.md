# Checklist — Data Minimisation & Privacy Shield

- [ ] Schemas contain only spec fields: report_type, product_name, batch_id, date_received, reporter_type,
      description (+ AE: event_description, event_onset_date). No patient name/age/DOB/contact fields.
- [ ] All Pydantic input models use `extra="forbid"` so stray keys (e.g. `patient_name`) are rejected.
- [ ] Free-text fields pass through `domain/guards.py::find_pii` (email, phone, SSN/ID-like numbers,
      DOB patterns, "patient name"/honorific + name heuristics).
- [ ] Actors are pseudonymous codes (`OP-xx`, `REV-xx`); no real names or emails stored.
- [ ] Audit `details_json` stores field names / enums / IDs / outcomes — never description text.
- [ ] Circuit-breaker audit stores only a signature hash, not raw arguments.
- [ ] Logs, exceptions and UI error messages do not echo full free-text fields.
- [ ] Seed data, tests and docs use the fictional naming conventions from CLAUDE.md.
- [ ] Governance hook output (`logs/claude_edit_audit.jsonl`) holds metadata only (no file content).

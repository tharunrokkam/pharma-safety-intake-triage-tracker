# pharma-intake-review — Milestones D & E

**Skill:** `.claude/skills/pharma-intake-review/SKILL.md` (procedure + 4 checklists)
**Scope:** `src/pharma_tracker/{domain,persistence,tools,agent,rag}`, `pages/`, `app.py`
**Date:** 2026-11-22. Run in the build session.

**Invocation note:** the skill was created during this same Claude Code session, and the session's skill
registry had not loaded it yet (`Unknown skill`). So the SKILL.md procedure was followed by hand, step by
step. To get native invocation evidence, open a new session and run `/pharma-intake-review`.

## Findings

| # | Severity | Checklist | File:line | Finding | Fix |
|---|----------|-----------|-----------|---------|-----|
| 1 | MAJOR | Data minimisation | `tools/registry.py` `register_failure` | `ref_id` from rejected arguments was copied into `audit_log.ref_id` whenever it was ≤16 chars, even if it did not match the REF pattern. Arbitrary user text (e.g. an email) could reach the audit table. | Only values matching `^REF-\d{4}-\d{4}$` are recorded; otherwise `NULL`. Regression test `test_invalid_ref_text_never_reaches_audit`. **Fixed** |
| 2 | MAJOR | Error handling | `tools/registry.py` `execute` | Only `DomainError` was caught. A `sqlite3.Error` (e.g. a race on the one-pending-approval unique index) would crash the LangGraph turn and the UI page. | `sqlite3.Error` → structured `storage_error` FieldError (feeds the breaker as an invalid call). Test `test_storage_errors_become_structured_errors`. **Fixed** |
| 3 | MINOR | Test coverage | `domain/schemas.py` `UpdateStatusArgs.note` | The PII shield on the status `note` field was not covered by a test. | Added `test_pii_in_status_note_rejected`. **Fixed** |
| 4 | MINOR | Error handling | `agent/service.py` `decide_approval` (direct path) | When the workflow thread is no longer in volatile memory, each decision uses a fresh breaker, so repeated invalid human decisions never trip it. | Accepted: decisions are human-driven, one click per attempt, and each failure is still audited. Documented here. |
| 5 | MINOR | Data minimisation | `domain/errors.py` `_echo` | Validation messages echo up to 24 chars of *identifier* fields (lot, ref, actor) back to the UI. They are never echoed for free text and never stored. | Accepted: helps operators fix typos and limited to an allow-list of identifier fields. |

## Non-negotiables (BLOCKER checks)

- No PII fields; `extra="forbid"`; PII regex shield on every free-text field — **PASS**
- No clinical/causality/reportability logic; clinical questions get a fixed refusal — **PASS**
- No network / LLM at runtime (`HF_HUB_OFFLINE=1`, `local_files_only=True`, Streamlit bound to localhost, telemetry off) — **PASS**
- Audit rows hold no description/event text; append-only triggers; hash chain verified — **PASS**
- `In Review -> Closed` needs an APPROVED approval from a different reviewer (repository-enforced) — **PASS**

## Summary

| Checklist | Result | Findings |
|---|---|---|
| Data minimisation | PASS (after fix) | 1 major fixed, 1 minor accepted |
| Error handling | PASS (after fix) | 1 major fixed, 1 minor accepted |
| Auditability | PASS | 0 |
| Test coverage | PASS (after fix) | 1 minor fixed — 137 tests, 97 % line coverage |

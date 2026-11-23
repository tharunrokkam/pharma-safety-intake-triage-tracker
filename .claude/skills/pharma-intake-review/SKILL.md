---
name: pharma-intake-review
description: Review code in the Pharma Safety Intake & Triage Tracker for data minimisation, error handling, auditability and test coverage. Use when asked to review intake, validation, persistence, workflow/HITL, circuit breaker, RAG or audit code, or before closing a milestone.
---

# Pharma Intake Review Skill

A repeatable, checklist-driven review for this repository. It complements (does not replace) the
always-on rules in `CLAUDE.md`.

## When to use
- At the end of each build milestone (A–E), before declaring it done.
- When a change touches `src/pharma_tracker/domain`, `persistence`, `tools`, `agent`, `rag`, `pages/`.
- When the user asks for a "pharma review", "intake review" or "compliance review" of code.

## Procedure
1. **Scope** — list the changed/target files (git diff, or the paths the user names). Read each fully.
2. **Apply every checklist** in `checklists/` to the scoped files:
   - `checklists/data_minimization.md`
   - `checklists/error_handling.md`
   - `checklists/auditability.md`
   - `checklists/test_coverage.md`
3. **Verify, don't assume** — for each candidate finding, open the code path and confirm it. Run
   `pytest -q` (and targeted tests) to confirm behaviour where practical.
4. **Report** in this exact format:

   | # | Severity | Checklist | File:line | Finding | Fix |
   |---|----------|-----------|-----------|---------|-----|

   Severity: `BLOCKER` (violates a CLAUDE.md hard boundary or loses audit integrity), `MAJOR`
   (incorrect behaviour / missing validation / missing test for a rule), `MINOR` (clarity, naming).
5. **Summary** — one line per checklist: PASS / FAIL with count of findings.
6. Record the review in `docs/reviews/<milestone>-review.md` (findings table + summary).

## Non-negotiables to always check (BLOCKER if violated)
- No PII fields, no real patient data, no clinical/causality/reportability logic or wording.
- No network calls / LLM calls at runtime.
- Audit rows never contain description or event free text; audit table has no UPDATE/DELETE path.
- `In Review -> Closed` cannot happen without an APPROVED approval by a different reviewer.

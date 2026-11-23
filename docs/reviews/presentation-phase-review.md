# pharma-intake-review — Presentation phase

**Invocation:** native `Skill(pharma-intake-review)` call in Claude Code (the skill was registered by the
harness this time; the earlier milestone D/E review followed the procedure by hand).
**Arguments:** review `scripts/load_test.py`, `scripts/capture_screenshots.py`, `scripts/seed_demo.py`, and the
fixes in `src/pharma_tracker/tools/registry.py`.
**Date:** 2026-11-22

## Findings

| # | Severity | Checklist | File:line | Finding | Fix |
|---|----------|-----------|-----------|---------|-----|
| 1 | MINOR | Error handling | `scripts/seed_demo.py:64` | The seeding loop used `assert ...ok` for control flow. Under `python -O` a failed seed would continue silently and produce a misleading demo. | Explicit check, `SystemExit` with the structured response. **Fixed** |
| 2 | MINOR | Data minimisation | `scripts/load_test.py:87` | Temp DBs (synthetic data only) were left in `%TEMP%` after the run. | `shutil.rmtree(tmp, ignore_errors=True)` at the end. **Fixed** |
| 3 | MINOR | Auditability | `scripts/capture_screenshots.py` | The script submits reports and approves closures in whatever app it targets. Pointed at the real app, it would pollute the demo DB and its audit trail. | Refuses to run unless `PHARMA_SCREENSHOT_DISPOSABLE=1` is set; the docstring documents the disposable-instance setup. Verified the refusal. **Fixed** |
| 4 | MINOR | Test coverage | `scripts/load_test.py` `synthetic_report` | No test showed that the load generator only produces valid, PII-free fictional reports. | `tests/unit/test_load_test_helpers.py` (300 generated reports validated and PII-screened, plus percentile maths). **Fixed** |
| 5 | MINOR | Error handling | `scripts/capture_screenshots.py:85` | The grid row is selected by a hard-coded pixel offset (row 8), which breaks if the seed data changes. | Accepted: presentation tooling only, not part of the app. Re-seed with `seed_demo.py --reset` before capturing. |

## Verification of `tools/registry.py` fixes (from the milestone D/E review)
- Line 177: only `^REF-\d{4}-\d{4}$` values reach `audit_log.ref_id`. Covered by `test_invalid_ref_text_never_reaches_audit`.
- Lines 164-168: `sqlite3.Error` becomes a structured `storage_error`, and only the exception *type* is logged, never
  the arguments. Covered by `test_storage_errors_become_structured_errors`.

## Non-negotiables
- No PII / clinical logic: generators use fictional products and texts prefixed "Fictional" — **PASS**
- No runtime network/LLM: encoders run offline; Playwright drives local Chrome against `localhost` only — **PASS**
- Audit integrity: the load test verifies the hash chain after concurrent writes — **PASS**
- HITL close rule unchanged — **PASS**

## Summary

| Checklist | Result | Findings |
|---|---|---|
| Data minimisation | PASS (after fix) | 1 minor fixed |
| Error handling | PASS (after fix) | 1 minor fixed, 1 minor accepted |
| Auditability | PASS (after fix) | 1 minor fixed |
| Test coverage | PASS (after fix) | 1 minor fixed |

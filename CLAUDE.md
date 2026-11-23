# CLAUDE.md — Pharma Safety Intake & Triage Tracker

Persistent contract for AI coding agents working in this repository. Read fully before any change.

## 1. What this project is
A **local-only training prototype** (Python 3.10+, Streamlit, SQLite, LangGraph, LangChain) that captures
fictional product quality complaints and suspected adverse event reports, validates them, tracks a
New -> In Review -> Closed workflow with a human-in-the-loop (HITL) close gate, keeps an immutable audit
trail, and answers historical/SOP questions with a 4-stage hybrid RAG pipeline.

Architecture blueprint: `docs/plan.md` and `docs/architecture.png`.

## 2. Hard scope boundaries (never violate)
- **Synthetic data only.** Never add real product names of real patients, real people, emails, phone
  numbers, dates of birth, addresses, or medical record identifiers — not in code, tests, seeds, or docs.
- **Non-clinical.** The system must NEVER assess causality, recommend treatment/dosing, determine
  regulatory reportability, or make any clinical or regulatory decision. Questions of that kind are routed
  to a fixed refusal (`agent/router.py`, rule `OUT_OF_SCOPE`). Do not weaken this.
- **Strictly local.** No cloud services, external APIs, remote DBs, telemetry, or LLM calls at runtime.
  Encoder weights are fetched once by `scripts/download_models.py`; runtime uses `HF_HUB_OFFLINE=1`.
- **No LLM.** The agent is deterministic: router = ordered rules, RAG answer = extractive quotes with
  citations, abstain when nothing passes the 0.40 rerank threshold. Never add generative text synthesis.

## 3. Architecture invariants
- Layers: `domain/` (pure, no I/O) -> `persistence/` (SQLite only) -> `tools/` (the ONLY write path) ->
  `agent/` (LangGraph) -> Streamlit `app.py` + `pages/`. UI never writes SQL directly.
- Every state change goes through `tools/registry.py` so validation, circuit breaker and audit apply to
  both the form and the chat agent.
- Status changes only via `domain/lifecycle.py`. `In Review -> Closed` requires an APPROVED row in
  `approvals` (repository enforces it) and the reviewer must differ from the requester.
- `audit_log` is append-only (SQLite triggers) and SHA-256 hash-chained. Never add UPDATE/DELETE paths.
- Audit `details` contain IDs, enums, field **names** and outcomes only — never description/event text.
- Constants for RAG (k1, b, top-k, RRF k, threshold, chunk sizes) live in `config.py` only.

## 4. Coding guidelines
- Python 3.10+ with type hints; Pydantic v2 (`ConfigDict(extra="forbid", str_strip_whitespace=True)`).
- Small modules, pure functions in `domain/`; no bare `except:`; raise typed errors from `domain/errors.py`.
- Never `print`/log report free text. Use pseudonymous actor codes `OP-01`, `REV-02`.
- Fictional naming conventions: products `Fictivex 20mg`, `Placebrix 5mg`, `Nullamycin 250mg`; lots
  `LOT-12345`; references `REF-2026-0001`.

## 5. Testing conventions
- `pytest -q` must pass before finishing any task. Tests live in `tests/unit` and `tests/integration`.
- Each test gets an isolated SQLite DB in `tmp_path` (see `tests/conftest.py`). Never touch `data/db/`.
- Fast tests use the deterministic `HashEmbeddings` / `KeywordCrossEncoder` fakes. Tests that need the
  real encoders are marked `@pytest.mark.models` and auto-skip when weights are not cached.
- Every new validator, transition rule, breaker boundary or retrieval stage needs a test.

## 6. Review & governance
- For code review use the skill `.claude/skills/pharma-intake-review` (checklists: data minimisation,
  error handling, auditability, test coverage).
- A PostToolUse hook (`.claude/settings.json`) logs file-edit events to `logs/claude_edit_audit.jsonl`
  (metadata only). Do not disable it or make it log file contents.

## 7. Commands
```
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt
python scripts/download_models.py      # one-time, then set HF_HUB_OFFLINE=1
python scripts/seed_demo.py            # 2 fictional reports + demo workflow
streamlit run app.py
pytest -q                              # fast suite;  pytest -m models  for real-encoder tests
```

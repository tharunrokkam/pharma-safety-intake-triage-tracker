# Plan — Pharma Safety Intake & Triage Tracker (LangChain + LangGraph, deterministic)

## 1. Context

A pharma enterprise currently logs product quality complaints and suspected adverse events in scattered spreadsheets. This causes missing mandatory fields, no review tracking and no audit trail. The capstone asks for a **local-only Streamlit training prototype** with:
- validated intake
- a tracker dashboard
- a New → In Review → Closed lifecycle
- an immutable audit log
- a **4-stage hybrid RAG** over past reports and SOPs
- a **5-step agentic control plane**

It also requires AI governance artifacts: CLAUDE.md, this plan, a review skill and a PostToolUse hook.

**Decisions already made**
- Workspace `c:\Users\vmadmin\Downloads\pharmaCapstone` is empty (greenfield). Python 3.12 is available.
- **No LLM** (your choice). LangGraph orchestrates a fully deterministic agent.
- LangChain supplies the retrieval components.
- RAG "generation" is an **extractive, citation-only composer**. Every sentence it returns is quoted verbatim from a retrieved chunk. This gives zero hallucination by construction.
- Persistence: **SQLite** (the spec allows JSON, but SQLite gives transactions, triggers and constraints for the audit trail).
- Strictly local. The HuggingFace encoder weights are downloaded **once** by a setup script. After that the app runs with `HF_HUB_OFFLINE=1`, so it makes no network calls at runtime.

**Hard boundaries (enforced in code and in CLAUDE.md)**
- Synthetic data only. No PII.
- The app never assesses causality, recommends treatment, decides reportability or makes clinical or regulatory decisions.

---

## 1a. FIRST STEP after approval: architecture infographic PNG (presentable Plan Mode output)

**Deliverable:** `docs/architecture.png`, a single landscape infographic (about 4800×3000 px at 200 dpi, white background, rounded colour-coded panels, numbered stage badges, arrows). It is rendered by a reproducible script, `scripts/render_architecture.py`, which uses **matplotlib** (installed into the project `.venv`; nothing is installed globally).

**Layout of the image (top to bottom, left to right):**
1. **Title banner.** "Pharma Safety Intake & Triage Tracker — Architecture (LangChain + LangGraph, deterministic, local-only)", plus three boundary chips: *Synthetic data only*, *Non-clinical*, *No cloud / no LLM*.
2. **Lane 1 – Users and UI (Streamlit).** Intake Operator (OP-xx) and Reviewer (REV-xx) icons, then 5 page boxes: New Report · Dashboard · Triage Approvals (HITL) · Knowledge Agent · Audit Trail.
3. **Lane 2 – LangGraph Control Plane** (the centre-piece, with numbered badges ①–⑤):
   input_guard → **③ Semantic Router** fanning out to 4 routes (Direct Response | Hybrid RAG | Intake Tool | Status Manager) → **① Pydantic Tool Validator + auto-repair** → **⑤ Circuit Breaker** (">2 identical invalid → HALT") → Execute Tool → **④ HITL Gate** (interrupt ⏸ / resume ▶, In Review→Closed only).
   Side box: **② Dual Memory**, with short-term (InMemorySaver ReAct trace: Thought→Action→Observation) and long-term (SQLite).
4. **Lane 3 – Hybrid RAG pipeline** (a horizontal funnel showing candidate counts shrinking):
   Corpus (SOPs + past reports) → Chunking 512/64 tokens → **Stage 1 BM25** (k1=1.3, b=0.75, top-50) ∥ **Stage 2 Bi-Encoder** (bge-small, cosine, top-50) → **Stage 3 RRF** (k=60) → **Stage 4 Cross-Encoder** (ms-marco, ≥0.40, top 3–5) → Extractive cited answer / abstain.
5. **Lane 4 – Persistence (SQLite).** Cylinders for reports · ae_details · ref_counters · status_transitions · approvals · audit_log (append-only + SHA-256 hash chain), plus the FAISS/BM25 index.
6. **Right column – Status lifecycle.** New → In Review → [HITL] → Closed, with ✗ marks on illegal transitions.
7. **Bottom strip – AI governance phases I–V.** CLAUDE.md · Plan Mode · Milestones A–D(+E) · Review Skill (4 checklists) · PostToolUse hook → `logs/claude_edit_audit.jsonl`.
8. **Legend** (colour per layer) and a footer naming the stack (Python 3.12, Streamlit, Pydantic v2, LangGraph, LangChain, FAISS, rank-bm25, sentence-transformers, SQLite).

**Steps:**
1. `python -m venv .venv`
2. `.venv\Scripts\pip install matplotlib`
3. Write the script.
4. Run it.
5. Open the PNG with the Read tool to check it visually (no overlapping text, readable fonts) and iterate.
6. Also export `docs/architecture.svg` (lossless, zoomable).

The PNG then becomes the visual "Plan Mode output" deliverable. This written plan goes alongside it as `docs/plan.md`.

---

## 2. Technology Stack

| Layer | Choice | Why |
|---|---|---|
| UI | `streamlit>=1.40` (multipage) | Spec mandate; lightweight local web UI |
| Schemas / tool validation | `pydantic>=2.7` | Strict types, regex, conditional validators |
| Orchestration | `langgraph>=0.2` (`StateGraph`, `interrupt`, `Command`, `InMemorySaver`) | Explicit state machine, native HITL interrupts, checkpointed short-term memory |
| Retrieval primitives | `langchain-core`, `langchain-community`, `langchain-text-splitters`, `langchain-huggingface` | `Document`, `BM25Retriever`, token-aware splitter, `HuggingFaceEmbeddings`, `FAISS`, `HuggingFaceCrossEncoder` |
| Sparse | `rank-bm25` (via `BM25Retriever`, `bm25_params={"k1":1.3,"b":0.75}`) | Stage 1 |
| Dense | `sentence-transformers` + `BAAI/bge-small-en-v1.5` (512-token max, 384-dim) + `faiss-cpu` | Stage 2. bge-small supports a full 512-token window (MiniLM truncates at 256) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Stage 4. Sigmoid-normalised score in [0,1] is compared to the 0.40 threshold |
| Persistence | `sqlite3` (stdlib), WAL mode | Long-term memory, audit trail |
| Tests | `pytest`, `pytest-cov` | Unit and integration |

---

## 3. Architecture

### 3.1 High-level component view

```
┌──────────────────────────── Streamlit UI (local) ────────────────────────────┐
│ New Report │ Dashboard/Tracker │ Triage Approvals (HITL) │ Knowledge Agent │ Audit │
└──────┬───────────────┬──────────────────┬──────────────────────┬────────────┬──┘
       │ form submit   │ status buttons   │ approve/reject        │ chat query │ read
       ▼               ▼                  ▼                       ▼            │
┌─────────────────────── LangGraph Control Plane (agent/graph.py) ─────────────┐ │
│ input_guard → semantic_router ─┬─► direct_response                           │ │
│                                ├─► rag_retrieve → rag_compose                │ │
│                                ├─► intake_tool ─┐                            │ │
│                                └─► status_mgr ──┤                            │ │
│                                     tool_validator (Pydantic + auto-repair)  │ │
│                                     circuit_breaker ──(tripped)──► halt      │ │
│                                     hitl_gate (interrupt) ◄── Command(resume)│ │
│ Short-term memory: AgentState (ReAct trace, messages) via InMemorySaver      │ │
└───────────────┬───────────────────────────────┬──────────────────────────────┘ │
                ▼                               ▼                                │
┌──────── Tool Layer (tools/) ───────┐  ┌──── Hybrid RAG (rag/) ──────────────┐  │
│ submit_intake_report, update_status│  │ BM25 top50 ─┐                       │  │
│ get_report, search_knowledge       │  │ Dense top50 ┴► RRF(k=60) ► CrossEnc │  │
└───────────────┬────────────────────┘  │ ≥0.40, top3–5 ► extractive composer │  │
                ▼                       └───────────────┬─────────────────────┘  │
┌──────── Long-term memory: SQLite (persistence/) ──────▼──────────────────────┐ │
│ reports │ ae_details │ ref_counters │ status_transitions │ approvals │ audit_log(append-only, hash-chained) │◄┘
└──────────────────────────────────────────────────────────────────────────────┘
        Corpus: data/sops/*.md (synthetic SOPs) + reports table → FAISS/BM25 index in data/index/
```

**Key design rule:** the Streamlit form and the chat agent both go through the **same tool layer**, so the same Pydantic validation, circuit breaker and audit apply to every path. The repository layer also refuses `In Review → Closed` unless an `APPROVED` approval row exists. This is defense in depth: the HITL gate can't be bypassed even if the graph is skipped.

### 3.2 LangGraph state machine

```mermaid
flowchart TD
  START --> input_guard
  input_guard -->|PII or clinical-scope violation| direct_response
  input_guard --> router
  router -->|GREETING / HELP| direct_response
  router -->|RAG_LOOKUP| rag_retrieve --> rag_compose --> END
  router -->|INTAKE| intake_tool --> tool_validator
  router -->|STATUS| status_mgr --> tool_validator
  tool_validator -->|valid| execute_tool
  tool_validator -->|invalid| circuit_breaker
  circuit_breaker -->|count ≤ 2| respond_error --> END
  circuit_breaker -->|count > 2 → OPEN| halt --> END
  execute_tool -->|In Review→Closed| hitl_gate
  hitl_gate -->|interrupt() … resume approve| commit_close --> END
  hitl_gate -->|resume reject| stay_in_review --> END
  execute_tool -->|other| END
  direct_response --> END
```

`AgentState` (TypedDict):
- `thread_id`, `user_input`, `actor_id`
- `route`
- `tool_call: {name, args}`, `validation_errors`
- `breaker: {signature, consecutive_failures, open}`
- `retrieval: {bm25, dense, fused, reranked}`
- `react_trace: list[{thought, action, observation}]`
- `response`, `pending_approval_id`

---

## 4. Spec-by-spec design

### 4.1 Functional requirements (spec §2)

| Requirement | Implementation |
|---|---|
| **Unique reference** `REF-2026-XXXX` | `domain/refgen.py`. A `ref_counters(year PK, last_seq)` row is incremented inside a `BEGIN IMMEDIATE` transaction, giving an atomic, gap-free, collision-proof ID per year. The format is `REF-{YYYY}-{seq:04d}`. Going past 9999 raises an explicit error. A `UNIQUE` constraint on `reports.ref_id` is the backstop. |
| **Categorisation** | `ReportType(StrEnum)`: `SUSPECTED_ADVERSE_EVENT = "Suspected Adverse Event"`, `PRODUCT_QUALITY_COMPLAINT = "Product Quality Complaint"` |
| **Core fields** | `product_name` (2–100 chars, allowed character set), `batch_id` (`^LOT-\d{5}$`), `date_received` (date, not in the future), `reporter_type` (`Healthcare Professional`, `Consumer`, `Pharmacist`, `Sales Representative`, `Other`), `description` (20–2000 chars) |
| **AE extension** | `event_description` and `event_onset_date` are **required only when** the type is AE. A `@model_validator(mode="after")` checks this, and also that onset ≤ date_received and onset is not in the future. There are no patient fields at all, and the model uses `extra="forbid"`, so unexpected keys such as `patient_name` are rejected. |
| **Mandatory validation** | Pydantic errors are mapped to **context-sensitive messages** by `domain/errors.py`, e.g. *"Event onset date is required for Suspected Adverse Event reports"* or *"Batch/Lot must look like LOT-12345 (you entered 'lot 1234')"*. The form shows them inline next to each field and also in a summary banner. |
| **PII shield** | `domain/guards.py` checks free-text fields for email, phone, SSN/NHS-like numbers, DOB patterns, and "patient name / Mr./Mrs. + Capitalised name" heuristics. A hit is a validation error ("Remove personal identifiers — synthetic data only"). |
| **Dashboard** | `st.dataframe` over `repository.list_reports(status=…, report_type=…)`. Sidebar multiselect filters, metrics row (counts by status/type), row selection opens a detail drawer with the transition buttons that are currently allowed. |
| **Lifecycle** | `domain/lifecycle.py`: `ALLOWED = {New: {In Review}, In Review: {Closed}}`. Closed is terminal. Skipping states, going backwards or a no-op transition raises `IllegalTransitionError`. `In Review → Closed` is marked `requires_hitl=True`. |
| **Audit trail** | `audit_log(id, ts_utc, actor_id, action, ref_id, from_status, to_status, details_json, prev_hash, row_hash)`. SQLite `BEFORE UPDATE/DELETE` triggers `RAISE(ABORT)`, so the table is append-only. A SHA-256 hash chain makes tampering detectable (`verify_chain()`). Payloads **never** include description or event text, only IDs, enums, field *names* and outcomes. `actor_id` is a pseudonymous operator code (e.g. `OP-01`, `REV-02`), not a person's name. |

### 4.2 Hybrid RAG pipeline (spec §5)

Corpus:
- `data/sops/*.md`: about 6 synthetic SOPs (AE intake, PQC handling, triage, closure criteria, lot recall lookup, data minimisation).
- Every saved report, rendered as a `Document` with metadata `{source:"report", ref_id, report_type, batch_id, status}`.

`rag/indexer.py` builds or refreshes the index on startup and incrementally after each new report.

| Stage | LangChain component | Spec parameters | Rationale |
|---|---|---|---|
| Chunking | `RecursiveCharacterTextSplitter.from_huggingface_tokenizer(bge_tokenizer, chunk_size=512, chunk_overlap=64)` | 512 / 64 tokens | Counts tokens with the **same tokenizer as the encoder**, so no chunk gets silently truncated. The 64-token overlap keeps sentences that span a boundary. |
| 1. BM25 sparse | `BM25Retriever.from_documents(chunks, k=50, bm25_params={"k1":1.3,"b":0.75}, preprocess_func=pharma_tokenize)` | k1=1.3, b=0.75, top-50 | `pharma_tokenize` keeps `LOT-88392` and `REF-2026-0001` as **single tokens** (the default whitespace split would break them), lowercases and drops stopwords. k1 saturates term frequency, so repeating "anaphylaxis" 20× doesn't dominate. b=0.75 normalises by length, so long SOPs aren't over-ranked. |
| 2. Dense bi-encoder | `HuggingFaceEmbeddings("BAAI/bge-small-en-v1.5", encode_kwargs={"normalize_embeddings":True})` + `FAISS(distance_strategy=MAX_INNER_PRODUCT)` | top-50, cosine | Normalised vectors make inner product equal to **cosine similarity**. This captures synonyms such as "difficulty breathing" ↔ "dyspnea". The index persists to `data/index/faiss`. |
| 3. RRF | Custom `rag/fusion.py::reciprocal_rank_fusion(rank_lists, k=60)` | k=60 | `score(d)=Σ 1/(60+rank_i(d))`. It uses only ranks, so BM25 scores (unbounded) and cosine scores ([-1,1]) need no normalisation. k=60 flattens the curve so a single #1 rank can't dominate. Chunks are de-duplicated by `chunk_id`. Written by hand (not `EnsembleRetriever`) so it is transparent and unit-testable. |
| 4. Cross-encoder rerank | `HuggingFaceCrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")` wrapped in `rag/rerank.py` | sigmoid score ≥ 0.40, keep top 3–5 | Joint attention over each (query, chunk) pair is far more precise than comparing vectors. Raw logits go through a sigmoid to land in [0,1], then the **0.40 threshold** is applied. At most 5 chunks are kept. If fewer than 3 pass, only the ones that passed are returned. |
| Compose | `rag/composer.py` (deterministic) | — | Returns the chunks as quoted bullet points with citations (`[SOP-03 §2]`, `[REF-2026-0004]`) and a rerank score, plus a fixed disclaimer. **If 0 chunks pass the threshold, it says so and refuses to answer** ("No sufficiently relevant records found"). It never synthesises new claims. |

The UI's Knowledge Agent page has a "Pipeline inspector" expander showing the BM25 top-10, the dense top-10, the RRF fused list and the rerank scores. This is the evidence for the multi-stage demo.

### 4.3 Agentic control plane (spec §6)

| Step | Implementation |
|---|---|
| **1. Type-safe tool validation** | `tools/registry.py` defines tools as LangChain `StructuredTool`s with Pydantic `args_schema`: `SubmitIntakeReportArgs`, `UpdateStatusArgs(ref_id: ^REF-\d{4}-\d{4}$, target_status: Status, actor_id: ^(OP\|REV)-\d{2}$, note)`, `SearchKnowledgeArgs`, `GetReportArgs`. Before validation, `tools/repair.py` applies **deterministic auto-repair**: it fuzzy-matches tool names (`difflib.get_close_matches`, cutoff 0.85, e.g. `submit_intake_reprot` → `submit_intake_report`), maps argument-key aliases (`lot`, `batch`, `lot_number` → `batch_id`), normalises `lot 88392` / `lot-88392` → `LOT-88392` and `in review`/`in_review` → `In Review`, and parses dates. Every repair is logged in the ReAct trace. If the repaired args still fail, the result is a structured `ToolValidationError{tool, errors:[{field, code, message}]}`. |
| **2. Dual memory** | **Short-term (volatile):** `AgentState.react_trace` holds Thought/Action/Observation entries and messages, checkpointed by LangGraph `InMemorySaver` keyed by `thread_id` (one per Streamlit session) and lost on restart. Because there is no LLM, each "Thought" is the deterministic rule explanation, e.g. *"Router: matched STATUS rule (REF id + verb 'close')"*. **Long-term (durable):** SQLite tables `reports`, `ae_details`, `status_transitions`, `approvals` and `audit_log`. |
| **3. Deterministic semantic router** | `agent/router.py` applies ordered, table-driven rules (see the list below). Routing happens **before** any tool or retrieval call and is 100% reproducible. The reason for each route goes into the trace. |
| **4. HITL gate** | When `update_status` targets `Closed` from `In Review`, the code inserts `approvals(status='PENDING', requested_by, ref_id)`, writes an `APPROVAL_REQUESTED` audit event and calls LangGraph `interrupt({...})`. The graph is frozen at that checkpoint. On the **Triage Approvals** page a reviewer (`REV-xx`, which **must differ from the requester**, for separation of duties) enters a mandatory justification and clicks Approve or Reject. That resumes the graph with `graph.invoke(Command(resume={decision, reviewer_id, justification}), config)`. Approval updates the approval row, commits the transition and writes `APPROVAL_GRANTED` and `STATUS_CHANGED`. Rejection keeps the report `In Review` and writes `APPROVAL_REJECTED`. The pending row also lives in SQLite, so the freeze survives an app restart (pending approvals are re-listed from the DB). |
| **5. Circuit breaker** | `tools/circuit_breaker.py`: `signature = sha256(tool_name + canonical_json(args))`. It counts **consecutive** invalid calls with the same signature. A success or a different signature resets the count. On the **3rd** consecutive identical invalid call (more than 2) it opens: execution halts, the `CIRCUIT_OPEN` audit event is written (signature hash only, no arguments), and the user sees "Execution halted after repeated invalid calls. Start a new session or correct the input." The breaker state lives per thread in `AgentState`, plus a guard in the tool layer so the form path is protected as well. |

The router's ordered rules:
1. **Out-of-scope / clinical guard.** Phrases like *"is X caused by"*, *"should I treat"*, *"is this reportable"*, *"dose"* get a fixed refusal (`direct_response`).
2. **Greeting / help** (`^(hi|hello|hey|help|thanks)\b`) → `direct_response`.
3. **Status** (`REF-\d{4}-\d{4}` + one of the verbs start review / move / close / set status) → `status_mgr`.
4. **Intake** (*new report*, *submit*, *log a complaint*, *report an adverse event*) → `intake_tool`.
5. **Default** → `rag_retrieve` (history and SOP questions).

---

## 5. Project Layout

```
pharmaCapstone/
├── CLAUDE.md                          # Phase I – persistent AI contract
├── README.md  requirements.txt  pyproject.toml (pytest, ruff config)
├── app.py                             # Streamlit entry / home
├── pages/
│   ├── 1_📝_New_Report.py  2_📊_Dashboard.py  3_✅_Triage_Approvals.py
│   ├── 4_🔎_Knowledge_Agent.py  5_🧾_Audit_Trail.py
├── src/pharma_tracker/
│   ├── config.py                      # paths, RAG constants (K1, B, TOPK=50, RRF_K=60, THRESH=0.40)
│   ├── domain/   enums.py schemas.py lifecycle.py refgen.py guards.py errors.py
│   ├── persistence/ db.py (connect, WAL, migrations) schema.sql repository.py audit.py
│   ├── tools/    registry.py repair.py circuit_breaker.py
│   ├── rag/      corpus.py chunking.py sparse.py dense.py fusion.py rerank.py composer.py pipeline.py indexer.py
│   └── agent/    state.py router.py nodes.py graph.py
├── data/ sops/*.md  seed/synthetic_reports.json   (db/ and index/ are gitignored)
├── scripts/ download_models.py  seed_demo.py  verify_audit_chain.py
├── tests/ unit/ (schemas, refgen, lifecycle, guards, repair, breaker, router, fusion, sparse tokenizer, audit)
│          integration/ (repository+audit, graph HITL interrupt/resume, breaker halt in graph, RAG end-to-end)
│          conftest.py (tmp SQLite, fake deterministic embeddings, @pytest.mark.models)
├── .claude/
│   ├── settings.json                  # Phase V – PostToolUse hook registration
│   ├── hooks/audit_file_edit.py
│   └── skills/pharma-intake-review/ SKILL.md  checklists/{data_minimization,error_handling,auditability,test_coverage}.md
├── logs/claude_edit_audit.jsonl       # hook output
└── docs/ plan.md (copy of this plan)  demo/ (screenshots, audit export)  reflection.md
```

---

## 6. Governance Artifacts (spec §4)

- **CLAUDE.md (Phase I).** Contains:
  - scope limits (non-clinical, synthetic only, local only, no LLM or network at runtime)
  - architecture rules (all writes go through the tool layer, the audit table is append-only, transitions only via `lifecycle.py`)
  - coding guidelines (type hints, Pydantic v2, no `print` of report text, small modules)
  - testing conventions (pytest, test DB in `tmp_path`, `@pytest.mark.models` for real-encoder tests, run `pytest -q` before finishing)
  - fictional-data handling rules (naming pattern `Fictivex 20mg`, `LOT-00000` style, never realistic patient data)

  It points to the skill for detailed review checklists. CLAUDE.md holds the **always-on invariants**. The skill holds **on-demand procedures**.
- **Skill (Phase IV)** `.claude/skills/pharma-intake-review/SKILL.md`. Its frontmatter `description` makes it trigger on "review intake code". It has steps to read the diff, apply the 4 checklists, and output findings in a severity table. The checklists cover:
  - Data minimisation: no PII fields, `extra="forbid"`, audit payloads free of description text
  - Error handling: every field has a contextual message, no bare except, breaker coverage
  - Auditability: every state change has an audit row, hash chain intact
  - Test coverage: each validator, transition and breaker boundary is tested

  It will be invoked during the code review of Milestone D, and that run is the evidence of invocation.
- **Hook (Phase V)** `.claude/settings.json`:
  ```json
  {"hooks":{"PostToolUse":[{"matcher":"Edit|Write|MultiEdit|NotebookEdit",
    "hooks":[{"type":"command","command":"python .claude/hooks/audit_file_edit.py"}]}]}}
  ```
  `audit_file_edit.py` reads the hook JSON from stdin. It appends `{ts_utc, event:"file_edit", tool_name, file_path (repo-relative), session_id_sha256[:12], file_sha256_after}` to `logs/claude_edit_audit.jsonl`. It **deliberately drops** `tool_input.content`, `old_string`, `new_string` and any description text. It always exits 0 (and never blocks), using stdlib only. It is deterministic: the same event always produces the same log shape, with no model judgement involved.

---

## 7. Incremental Milestones (Phase III)

0. **Governance first.** CLAUDE.md, `.claude/settings.json`, the hook script and the skill folder. Do a test edit and confirm the hook writes a JSONL line.
1. **A – Skeleton.** pyproject/requirements, package layout, `config.py`, `db.py` + `schema.sql` migrations, Streamlit shell with empty pages, `pytest` running green on a smoke test.
2. **B – Intake form and schemas.** Enums, Pydantic models, guards, error mapping, `refgen`, and the New Report page with conditional AE fields. Unit tests for every validation rule.
3. **C – Validation and persistence.** Repository, append-only hash-chained audit, tool registry + repair + circuit breaker, and the form wired through the `submit_intake_report` tool. Integration tests for storage integrity, the audit triggers and the breaker limit.
4. **D – Dashboard and workflow lifecycle.** Dashboard filters, the lifecycle, the LangGraph graph (router, status manager, HITL interrupt/resume), and the Triage Approvals and Audit Trail pages. Tests for illegal transitions and HITL freeze/resume. **Invoke the `pharma-intake-review` skill.**
5. **E – Hybrid RAG + Knowledge Agent.** Synthetic SOPs, chunking, the 4 stages, the composer, the Knowledge Agent chat page with the pipeline inspector. Unit tests for RRF math and the tokenizer, plus model-marked retrieval tests (exact lot match via BM25, "difficulty breathing" → dyspnea report via dense, threshold abstain on an off-topic query).
6. **Demo and reflection.**
   - Run `seed_demo.py` to create 2 fictional reports: 1 AE (`Fictivex 20mg`, `LOT-88392`, dyspnea) and 1 PQC (`Placebrix 5mg`, `LOT-10457`, cracked tablets).
   - Move one through New → In Review → (HITL approve) → Closed.
   - Run a multi-stage RAG query.
   - Export the audit trail plus `verify_audit_chain.py` output into `docs/demo/`.
   - Draft `docs/reflection.md` answering the 5 defense questions.

---

## 8. Test Strategy (Deliverable 6)

- **Schema validation:** valid AE/PQC; each missing field; bad lot formats (`LOT-1234`, `lot88392`); future dates; onset > received; AE fields missing for an AE report; extra `patient_name` key rejected; PII strings rejected.
- **Storage integrity:** sequential unique refs, including concurrent generation; UPDATE/DELETE on `audit_log` raises; hash chain verifies, and breaks when a row is tampered with via a raw `PRAGMA`-disabled copy; no description text appears in any audit row.
- **Lifecycle and HITL:**
  - every illegal transition raises
  - a Closed request leaves the status `In Review` until resume
  - reject keeps the report In Review
  - the reviewer can't be the requester
  - the repository refuses to close without an approval
- **Circuit breaker:** 2 identical invalid calls stay closed, the 3rd opens it; a success resets; a different signature resets; inside the graph, the halt route ends with `CIRCUIT_OPEN` in the audit.
- **Router:** table-driven cases for all 5 rules, including clinical-question refusals.
- **RAG:**
  - RRF numerics (hand-computed ranks with k=60)
  - the tokenizer keeps `LOT-88392` whole
  - BM25 params are applied
  - the threshold filter and the top-5 cap
  - the composer abstains when nothing passes
  - real-model tests are `@pytest.mark.models` and skipped if the weights aren't cached
  - fast tests use a deterministic hash-embedding fake

---

## 9. Verification (end-to-end)

1. `python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt`
2. `python scripts/download_models.py` (one time; caches bge-small and the ms-marco cross-encoder), then `set HF_HUB_OFFLINE=1`
3. `pytest -q --cov=pharma_tracker` → all green; then `pytest -m models` for the real-encoder retrieval tests
4. `python scripts/seed_demo.py` → 2 fictional reports + SOP index
5. `streamlit run app.py` and walk through:
   - submit a report with a missing onset date → contextual error
   - submit a valid report → `REF-2026-000N` is issued
   - Dashboard filters
   - New → In Review
   - request Close → appears in Triage Approvals and the status stays In Review
   - approve as `REV-02` → Closed
   - in the Knowledge Agent, ask "any history of difficulty breathing with LOT-88392?" → inspector shows BM25/dense/RRF/rerank, and the answer cites `REF-2026-0001` and the SOP
   - ask "should the patient stop the drug?" → refusal
   - send an invalid status command 3× → circuit breaker halt
6. Audit Trail page shows every event. `python scripts/verify_audit_chain.py` → "chain OK".
7. Check that `logs/claude_edit_audit.jsonl` has entries for every edit made during the build and no file content.

---

## 10. Defense / Reflection outline (spec §8 → docs/reflection.md)

1. **CLAUDE.md vs skills.** CLAUDE.md holds invariants that are always loaded (scope, safety, architecture rules). Skills hold task-specific procedures that load on demand. This keeps context lean and makes reviews repeatable.
2. **Plan Mode.** It surfaced edge cases before any code existed:
   - conditional AE fields
   - onset ≤ received
   - lot tokenisation for BM25
   - the 0.40 threshold needing sigmoid-normalised scores
   - HITL needing a repository-level guard
   - the 256-token MiniLM limit vs the 512-token chunks
3. **Deterministic hooks.** The harness runs them on every matching event as fixed code with a fixed output schema, so they can't be skipped, talked out of running, or vary like model judgement.
4. **RAG precision.**
   - BM25 gives exact lot and code recall.
   - The bi-encoder gives synonym recall.
   - RRF merges the two without score-scale bias.
   - The cross-encoder gives precise ranking, and the threshold makes it abstain.
   - The extractive composer means the system can only repeat what it retrieved.
5. **Production readiness.**
   - SSO/RBAC with real identity
   - encryption at rest
   - validated GxP/21 CFR Part 11 e-signatures for HITL
   - WORM/externally anchored audit storage
   - a server database (Postgres) with backups
   - model validation and change control
   - PII DLP scanning
   - integration with a validated PV system
   - threat modelling and pen testing
   - monitoring
   - CSV/IQ-OQ-PQ validation documentation

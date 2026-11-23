# Capstone Defense & Technical Reflection

## 1. Architectural boundary: CLAUDE.md vs. modular skills

**CLAUDE.md** is loaded into every agent session. So it holds only the *invariants* that must never be broken,
whatever the task:
- scope limits (synthetic data, non-clinical, local only, no LLM)
- the layering rule: the tool layer is the only write path
- the append-only audit table
- coding and testing conventions
- the fictional-data naming patterns

Those rules are short, stable and apply to every edit.

The **pharma-intake-review skill** holds a *procedure* that only matters at review time: the step-by-step review,
the four detailed checklists (data minimisation, error handling, auditability, test coverage) and the report
format. Putting that in CLAUDE.md would spend context on every unrelated task and make the contract harder to
read. Keeping it in a skill means it loads on demand and is versioned separately. It can also grow (more
checklists, a severity rubric) without changing the core contract. In short, CLAUDE.md says *what must always be
true*, and the skill says *how to check that it is true*.

## 2. Planning efficiency: what Plan Mode surfaced before code existed

Writing the plan and the architecture diagram first forced the data flow to be explicit, and that exposed these
edge cases early:
- **Conditional AE fields.** These need field-level validators that read `report_type`, so errors attach to the
  right form field. A whole-model validator would only produce one unlocated error.
- **Onset ≤ received, and no future dates.** These are cross-field rules that the form widgets alone can't enforce.
- **BM25 tokenisation.** The default whitespace tokenizer would break `LOT-88392` apart. A custom `pharma_tokenize`
  was specified up front.
- **The 0.40 threshold only means something on a [0,1] scale.** Implementation then confirmed that the cross-encoder
  returns raw logits (−11.3 for an unrelated pair), so sigmoid calibration is required.
- **Encoder window vs. chunk size.** MiniLM bi-encoders truncate at 256 tokens, so the spec's 512-token chunks would
  be silently cut. That led to choosing bge-small (512 tokens) and splitting with its own tokenizer.
- **The HITL gate has to hold even outside the graph.** That led to a repository-level check ("no Closed without an
  APPROVED approval") and a restart path, because the LangGraph checkpointer is deliberately volatile.
- **One write path.** Routing the form and the dashboard through the same graph as the chat means validation, the
  circuit breaker and the audit can't be bypassed.

## 3. Governance control: why hooks are deterministic

The PostToolUse hook is registered in `.claude/settings.json`, and the **harness** runs it after every matching
tool event. The model doesn't decide whether it runs, can't be talked out of it, and can't change what it logs. The
hook is fixed code (`audit_file_edit.py`, stdlib only) with a fixed output schema:
- timestamp
- tool
- relative path
- hashed session
- file SHA-256

So the same event always produces the same kind of record. It always exits 0, so it never blocks work, and it
structurally can't log content because it never reads `content`/`old_string`/`new_string`.

Model-driven evaluation, such as asking the agent to "remember to log edits" or to judge compliance, is
probabilistic. It can be skipped, worded differently each time, or affected by prompt injection. That makes it
unsuitable as audit evidence. The same split appears inside the app: guards, router, validator, breaker and
lifecycle are all rule-based code, never model judgement.

## 4. Multi-stage RAG precision: why the combination removes hallucination

Each stage covers a different failure mode:
- **BM25** guarantees recall of *exact identifiers* (lot numbers, reference ids, codes), which embeddings handle
  poorly. k1 = 1.3 caps term-frequency inflation, and b = 0.75 stops long SOP sections from drowning short reports.
- **The bi-encoder** guarantees recall of *meaning*, e.g. "difficulty breathing" ↔ "shortness of breath / dyspnea".
  In the demo it surfaced REF-2026-0001, which shares no key term with the query.
- **RRF (k = 60)** merges two scales that can't be compared (unbounded BM25 scores and cosine similarity) using
  ranks alone. Nothing needs tuning, and no single list can dominate.
- **The cross-encoder** reads the query and each chunk *together*, so it can judge relevance precisely. The
  **0.40 threshold** turns "least bad match" into "nothing relevant", which lets the system decline to answer.
  The off-topic demo query scored 0.00 on every candidate.

The final step is what actually removes hallucination: the **extractive composer**. No LLM writes the answer. Every
sentence is quoted verbatim from a chunk that passed the threshold and carries its citation. If nothing passes, the
system says so. Retrieval precision decides *which* evidence is shown, and the extractive design means nothing else
can appear.

## 5. Production readiness: mandatory changes before real deployment

- **Identity & access:**
  - enterprise SSO
  - RBAC replacing the pseudonymous actor picker
  - separation of duties enforced against verified identities
  - session management
- **Regulatory compliance:**
  - computer system validation (IQ/OQ/PQ)
  - 21 CFR Part 11 / EU Annex 11 electronic signatures for the HITL approval
  - a validated change-control process
  - a formal SOP set
  - integration with the validated pharmacovigilance safety database, which stays the system of record
- **Data protection:**
  - real PHI/PII handling under GDPR/HIPAA (DPIA, retention and deletion policies)
  - encryption at rest and in transit
  - a professional DLP/PII detection service instead of regexes
  - field-level access control
- **Audit integrity:**
  - WORM or externally anchored storage for the hash chain
  - time synchronisation and signed timestamps
  - SIEM forwarding and alerting
- **Infrastructure:**
  - a server RDBMS (PostgreSQL) with backups, high availability and migrations
  - a persistent LangGraph checkpointer (Postgres saver)
  - containerised deployment behind TLS
  - secrets management
  - monitoring and logging
  - capacity tests
- **ML governance:**
  - pinned, validated model versions with checksums
  - a retrieval evaluation set and drift monitoring
  - documented threshold calibration
  - change control for models and SOP corpora
- **Security:**
  - threat model
  - penetration test
  - dependency and SBOM scanning
  - input-size limits and rate limiting
  - prompt-injection review of any future LLM use

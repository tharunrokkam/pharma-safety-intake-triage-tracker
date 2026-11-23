# Demonstration walkthrough (generated 2026-11-22T04:42:46+00:00)

RAG mode: `real (BAAI/bge-small-en-v1.5 + cross-encoder/ms-marco-MiniLM-L-6-v2)`

Seeded 6 historical fictional reports (REF-2026-0001..0006).

### Validation demo - AE missing onset date and malformed lot
- route: `TOOL` (rule `R_PRESET`)  interrupted: `False`  halted: `False`

> I couldn't complete that request:
> 
> - **Batch/Lot number**: Batch/Lot number must be LOT- followed by exactly 5 digits, e.g. LOT-12345 (you entered 'LOT-883').
> - **Event onset date**: Event onset date is required for Suspected Adverse Event reports.
> 
> _Invalid attempt 1 of 2 allowed for this exact call - repeating it unchanged again will trip the circuit breaker._

| step | thought | action | observation |
|---|---|---|---|
| 1 | Structured UI call - free-text guards not needed (Pydantic schemas include the PII shield). | `pass` | tool=submit_intake_report |
| 2 | Input is a structured UI action; route straight to validation. | `route -> TOOL` | tool=submit_intake_report |
| 3 | Validate tool call against the strict Pydantic schema (with auto-repair). | `validate(submit_intake_report)` | 2 validation error(s) |
| 4 | Return structured validation errors so the user can correct the input. | `circuit_breaker -> CLOSED (count)` | consecutive_failures=1 |

### Demo report 1 - Suspected Adverse Event (lot auto-repaired)
- route: `TOOL` (rule `R_PRESET`)  interrupted: `False`  halted: `False`

> Report **REF-2026-0007** created with status **New**.
> 
> _Auto-repairs applied: batch_id normalised to LOT-88392_

| step | thought | action | observation |
|---|---|---|---|
| 1 | Structured UI call - free-text guards not needed (Pydantic schemas include the PII shield). | `pass` | tool=submit_intake_report |
| 2 | Input is a structured UI action; route straight to validation. | `route -> TOOL` | tool=submit_intake_report |
| 3 | Validate tool call against the strict Pydantic schema (with auto-repair). | `validate(submit_intake_report)` | valid; auto-repairs: batch_id normalised to LOT-88392 |
| 4 | Execute the validated call through its LangChain StructuredTool. | `submit_intake_report(report_type=Suspected Adverse Event, batch_id=LOT-88392)` | success |

### Demo report 2 - Product Quality Complaint
- route: `TOOL` (rule `R_PRESET`)  interrupted: `False`  halted: `False`

> Report **REF-2026-0008** created with status **New**.

| step | thought | action | observation |
|---|---|---|---|
| 1 | Structured UI call - free-text guards not needed (Pydantic schemas include the PII shield). | `pass` | tool=submit_intake_report |
| 2 | Input is a structured UI action; route straight to validation. | `route -> TOOL` | tool=submit_intake_report |
| 3 | Validate tool call against the strict Pydantic schema (with auto-repair). | `validate(submit_intake_report)` | valid |
| 4 | Execute the validated call through its LangChain StructuredTool. | `submit_intake_report(report_type=Product Quality Complaint, batch_id=LOT-10457)` | success |

### Chat: move REF-2026-0007 to in review
- route: `STATUS` (rule `R4_STATUS`)  interrupted: `False`  halted: `False`

> **REF-2026-0007** moved **New -> In Review**.

| step | thought | action | observation |
|---|---|---|---|
| 1 | Screen input for personal identifiers and clinical-decision requests. | `input_guard(PII shield, non-clinical scope filter)` | clean |
| 2 | Router: matched rule R4_STATUS (reference id + workflow/lookup verb). | `route -> STATUS` | deterministic routing complete |
| 3 | Extract reference id and target status from the workflow request. | `extract_status_call -> update_status` | args: {'ref_id': 'REF-2026-0007', 'actor_id': 'OP-01', 'target_status': 'In Review'} |
| 4 | Validate tool call against the strict Pydantic schema (with auto-repair). | `validate(update_status)` | valid |
| 5 | Execute the validated call through its LangChain StructuredTool. | `update_status(ref_id=REF-2026-0007, target_status=In Review)` | success |

### Chat: close REF-2026-0007 -> HITL interrupt (state frozen)
- route: `STATUS` (rule `R4_STATUS`)  interrupted: `True`  halted: `False`

> **Human-in-the-loop gate:** Closure of REF-2026-0007 requires reviewer approval (In Review -> Closed). Approval #1 is PENDING in *Triage Approvals*; the report stays **In Review** (frozen) until a different reviewer approves or rejects it.

| step | thought | action | observation |
|---|---|---|---|
| 1 | Screen input for personal identifiers and clinical-decision requests. | `input_guard(PII shield, non-clinical scope filter)` | clean |
| 2 | Router: matched rule R4_STATUS (reference id + workflow/lookup verb). | `route -> STATUS` | deterministic routing complete |
| 3 | Extract reference id and target status from the workflow request. | `extract_status_call -> update_status` | args: {'ref_id': 'REF-2026-0007', 'actor_id': 'OP-01', 'target_status': 'Closed'} |
| 4 | Validate tool call against the strict Pydantic schema (with auto-repair). | `validate(update_status)` | valid |
| 5 | Execute the validated call through its LangChain StructuredTool. | `update_status(ref_id=REF-2026-0007, target_status=Closed)` | HITL required - approval #1 created (PENDING) |

Status while frozen: **In Review**; pending approvals: [1]


### Reviewer REV-02 approves -> LangGraph resume
- route: `STATUS` (rule `R4_STATUS`)  interrupted: `False`  halted: `False`

> Reviewer **REV-02** approved closure of **REF-2026-0007** - status is now **Closed**.

| step | thought | action | observation |
|---|---|---|---|
| 1 | Screen input for personal identifiers and clinical-decision requests. | `input_guard(PII shield, non-clinical scope filter)` | clean |
| 2 | Router: matched rule R4_STATUS (reference id + workflow/lookup verb). | `route -> STATUS` | deterministic routing complete |
| 3 | Extract reference id and target status from the workflow request. | `extract_status_call -> update_status` | args: {'ref_id': 'REF-2026-0007', 'actor_id': 'OP-01', 'target_status': 'Closed'} |
| 4 | Validate tool call against the strict Pydantic schema (with auto-repair). | `validate(update_status)` | valid |
| 5 | Execute the validated call through its LangChain StructuredTool. | `update_status(ref_id=REF-2026-0007, target_status=Closed)` | HITL required - approval #1 created (PENDING) |
| 6 | Human reviewer decision received; record it via decide_approval. | `hitl_gate(resume) -> decide_approval` | APPROVED -> status Closed |

Left REF-2026-0002 with a PENDING closure approval (interrupted=True) for the UI demo.

### Hybrid RAG query: "any history of difficulty breathing with LOT-88392?"
- route: `RAG` (rule `R6_DEFAULT_RAG`)  interrupted: `False`  halted: `False`

> **Retrieved evidence - 3 source(s), extractive (no generated content):**
> 
> 1. **[REF-2026-0007]** (Report, relevance 0.98)  
>    > "Description: Physician's office called to report that the reporter experienced difficulty breathing and throat tightness shortly after a dose from this batch. … Event: Difficulty breathing with throat tightness within thirty minutes of use; resolved after on-site care."
> 2. **[SOP-05 §2]** (SOP, relevance 0.98)  
>    > "SOP-05 Batch and Lot Lookup (Fictional Training SOP) - 2. … The hybrid search combines exact keyword matching for identifiers with semantic matching for descriptions, so both "LOT-88392" and "trouble breathing" style queries return relevant history."
> 3. **[REF-2026-0001]** (Report, relevance 0.47)  
>    > "Reference REF-2026-0001 - Suspected Adverse Event … Product: Fictivex 20mg | Batch/Lot: LOT-88392 | Received: 2026-03-04 | Reporter: Pharmacist"
> 
> _Retrieval only - quoted from fictional records/SOPs. This tool does not assess causality, recommend treatment or determine regulatory reportability._

| step | thought | action | observation |
|---|---|---|---|
| 1 | Screen input for personal identifiers and clinical-decision requests. | `input_guard(PII shield, non-clinical scope filter)` | clean |
| 2 | Router: matched rule R6_DEFAULT_RAG (knowledge / historical lookup (default)). | `route -> RAG` | deterministic routing complete |
| 3 | Historical/SOP question -> run 4-stage hybrid retrieval. | `search_knowledge(query)` | dispatched to validator |
| 4 | Validate tool call against the strict Pydantic schema (with auto-repair). | `validate(search_knowledge)` | valid |
| 5 | Execute the validated call through its LangChain StructuredTool. | `search_knowledge()` | success |
| 6 | Compose an extractive, cited answer from chunks above the 0.40 rerank threshold. | `extractive_composer` | abstained=False; citations=['REF-2026-0007', 'SOP-05 §2', 'REF-2026-0001'] |

| stage | candidates | top-3 (citation: score) |
|---|---|---|
| 1 BM25 (k1=1.3,b=0.75) | 7 | REF-2026-0007: 6.4033, SOP-05 §2: 5.9950, SOP-01 §4: 3.9145 |
| 2 Bi-encoder cosine | 36 | REF-2026-0007: 0.7024, REF-2026-0001: 0.6562, SOP-01 §4: 0.6553 |
| 3 RRF k=60 | 36 | REF-2026-0007: 0.0328, SOP-05 §2: 0.0318, SOP-01 §4: 0.0317 |
| 4 Cross-encoder (sigmoid) | 36 | REF-2026-0007: 0.9793, SOP-05 §2: 0.9790, REF-2026-0001: 0.4674 |
| Final >= 0.40, max 5 | 3 | REF-2026-0007: 0.9793, SOP-05 §2: 0.9790, REF-2026-0001: 0.4674 |

### Off-topic query -> abstain
- route: `RAG` (rule `R6_DEFAULT_RAG`)  interrupted: `False`  halted: `False`

> No sufficiently relevant records found (no candidate reached the 0.40 relevance threshold). I will not guess - try different keywords, a batch number (LOT-12345) or a reference id.

| step | thought | action | observation |
|---|---|---|---|
| 1 | Screen input for personal identifiers and clinical-decision requests. | `input_guard(PII shield, non-clinical scope filter)` | clean |
| 2 | Router: matched rule R6_DEFAULT_RAG (knowledge / historical lookup (default)). | `route -> RAG` | deterministic routing complete |
| 3 | Historical/SOP question -> run 4-stage hybrid retrieval. | `search_knowledge(query)` | dispatched to validator |
| 4 | Validate tool call against the strict Pydantic schema (with auto-repair). | `validate(search_knowledge)` | valid |
| 5 | Execute the validated call through its LangChain StructuredTool. | `search_knowledge()` | success |
| 6 | Compose an extractive, cited answer from chunks above the 0.40 rerank threshold. | `extractive_composer` | abstained=True; citations=[] |

### Clinical question -> refusal
- route: `OUT_OF_SCOPE` (rule `R2_CLINICAL_SCOPE`)  interrupted: `False`  halted: `False`

> I can't help with causality assessment. This training tool only captures, tracks and retrieves fictional intake records. It never assesses causality, recommends treatment, determines regulatory reportability or makes clinical/regulatory decisions. Please route this question to a qualified pharmacovigilance professional through your enterprise PV system.

| step | thought | action | observation |
|---|---|---|---|
| 1 | Screen input for personal identifiers and clinical-decision requests. | `input_guard(PII shield, non-clinical scope filter)` | blocked: R2_CLINICAL_SCOPE |
| 2 | No tool or retrieval needed. | `direct_response` | OUT_OF_SCOPE template returned |

### Circuit breaker attempt 1
- route: `STATUS` (rule `R4_STATUS`)  interrupted: `False`  halted: `False`

> I couldn't complete that request:
> 
> - **Request**: No report found with reference REF-2026-0999.
> 
> _Invalid attempt 1 of 2 allowed for this exact call - repeating it unchanged again will trip the circuit breaker._

| step | thought | action | observation |
|---|---|---|---|
| 1 | Screen input for personal identifiers and clinical-decision requests. | `input_guard(PII shield, non-clinical scope filter)` | clean |
| 2 | Router: matched rule R4_STATUS (reference id + workflow/lookup verb). | `route -> STATUS` | deterministic routing complete |
| 3 | Extract reference id and target status from the workflow request. | `extract_status_call -> update_status` | args: {'ref_id': 'REF-2026-0999', 'actor_id': 'OP-01', 'target_status': 'In Review'} |
| 4 | Validate tool call against the strict Pydantic schema (with auto-repair). | `validate(update_status)` | valid |
| 5 | Execute the validated call through its LangChain StructuredTool. | `update_status(ref_id=REF-2026-0999, target_status=In Review)` | rejected by domain rules: not_found |
| 6 | Return structured validation errors so the user can correct the input. | `circuit_breaker -> CLOSED (count)` | consecutive_failures=1 |

### Circuit breaker attempt 2
- route: `STATUS` (rule `R4_STATUS`)  interrupted: `False`  halted: `False`

> I couldn't complete that request:
> 
> - **Request**: No report found with reference REF-2026-0999.
> 
> _Invalid attempt 2 of 2 allowed for this exact call - repeating it unchanged again will trip the circuit breaker._

| step | thought | action | observation |
|---|---|---|---|
| 1 | Screen input for personal identifiers and clinical-decision requests. | `input_guard(PII shield, non-clinical scope filter)` | clean |
| 2 | Router: matched rule R4_STATUS (reference id + workflow/lookup verb). | `route -> STATUS` | deterministic routing complete |
| 3 | Extract reference id and target status from the workflow request. | `extract_status_call -> update_status` | args: {'ref_id': 'REF-2026-0999', 'actor_id': 'OP-01', 'target_status': 'In Review'} |
| 4 | Validate tool call against the strict Pydantic schema (with auto-repair). | `validate(update_status)` | valid |
| 5 | Execute the validated call through its LangChain StructuredTool. | `update_status(ref_id=REF-2026-0999, target_status=In Review)` | rejected by domain rules: not_found |
| 6 | Return structured validation errors so the user can correct the input. | `circuit_breaker -> CLOSED (count)` | consecutive_failures=2 |

### Circuit breaker attempt 3
- route: `STATUS` (rule `R4_STATUS`)  interrupted: `False`  halted: `True`

> Execution halted: the same tool was called with the same invalid arguments more than 2 consecutive times (circuit breaker OPEN). Start a new session (sidebar -> 'Reset session') or correct the input.

| step | thought | action | observation |
|---|---|---|---|
| 1 | Screen input for personal identifiers and clinical-decision requests. | `input_guard(PII shield, non-clinical scope filter)` | clean |
| 2 | Router: matched rule R4_STATUS (reference id + workflow/lookup verb). | `route -> STATUS` | deterministic routing complete |
| 3 | Extract reference id and target status from the workflow request. | `extract_status_call -> update_status` | args: {'ref_id': 'REF-2026-0999', 'actor_id': 'OP-01', 'target_status': 'In Review'} |
| 4 | Validate tool call against the strict Pydantic schema (with auto-repair). | `validate(update_status)` | valid |
| 5 | Execute the validated call through its LangChain StructuredTool. | `update_status(ref_id=REF-2026-0999, target_status=In Review)` | rejected by domain rules: not_found |
| 6 | Same invalid call seen 3 consecutive times (> 2). | `circuit_breaker -> OPEN` | execution halted |

### Audit trail (23 events, chain OK)

| id | ts_utc | actor | action | ref | from -> to | details |
|---|---|---|---|---|---|---|
| 1 | 2026-11-22T04:42:46+00:00 | OP-01 | REPORT_CREATED | REF-2026-0001 |  -> New | `{"batch_id":"LOT-88392","fields_captured":["report_type","product_name","batch_id","date_received","reporter_type","description","event_description","event_onset_date"],"report_type":"Suspected Adverse Event"}` |
| 2 | 2026-11-22T04:42:46+00:00 | OP-01 | REPORT_CREATED | REF-2026-0002 |  -> New | `{"batch_id":"LOT-10457","fields_captured":["report_type","product_name","batch_id","date_received","reporter_type","description"],"report_type":"Product Quality Complaint"}` |
| 3 | 2026-11-22T04:42:46+00:00 | OP-01 | REPORT_CREATED | REF-2026-0003 |  -> New | `{"batch_id":"LOT-55120","fields_captured":["report_type","product_name","batch_id","date_received","reporter_type","description","event_description","event_onset_date"],"report_type":"Suspected Adverse Event"}` |
| 4 | 2026-11-22T04:42:46+00:00 | OP-01 | REPORT_CREATED | REF-2026-0004 |  -> New | `{"batch_id":"LOT-88392","fields_captured":["report_type","product_name","batch_id","date_received","reporter_type","description"],"report_type":"Product Quality Complaint"}` |
| 5 | 2026-11-22T04:42:47+00:00 | OP-01 | REPORT_CREATED | REF-2026-0005 |  -> New | `{"batch_id":"LOT-10457","fields_captured":["report_type","product_name","batch_id","date_received","reporter_type","description","event_description","event_onset_date"],"report_type":"Suspected Adverse Event"}` |
| 6 | 2026-11-22T04:42:47+00:00 | OP-01 | REPORT_CREATED | REF-2026-0006 |  -> New | `{"batch_id":"LOT-55120","fields_captured":["report_type","product_name","batch_id","date_received","reporter_type","description"],"report_type":"Product Quality Complaint"}` |
| 7 | 2026-11-22T04:42:47+00:00 | OP-01 | VALIDATION_FAILED |  |  ->  | `{"codes":["ae_field_required","string_pattern_mismatch"],"consecutive_failures":1,"fields":["batch_id","event_onset_date"],"tool":"submit_intake_report"}` |
| 8 | 2026-11-22T04:42:47+00:00 | OP-01 | REPORT_CREATED | REF-2026-0007 |  -> New | `{"batch_id":"LOT-88392","fields_captured":["report_type","product_name","batch_id","date_received","reporter_type","description","event_description","event_onset_date"],"report_type":"Suspected Adverse Event"}` |
| 9 | 2026-11-22T04:42:47+00:00 | OP-02 | REPORT_CREATED | REF-2026-0008 |  -> New | `{"batch_id":"LOT-10457","fields_captured":["report_type","product_name","batch_id","date_received","reporter_type","description"],"report_type":"Product Quality Complaint"}` |
| 10 | 2026-11-22T04:42:47+00:00 | OP-01 | STATUS_CHANGED | REF-2026-0007 | New -> In Review | `{}` |
| 11 | 2026-11-22T04:42:47+00:00 | OP-01 | APPROVAL_REQUESTED | REF-2026-0007 | In Review -> Closed | `{"approval_id":1,"gate":"HITL"}` |
| 12 | 2026-11-22T04:42:47+00:00 | REV-02 | APPROVAL_GRANTED | REF-2026-0007 |  ->  | `{"approval_id":1,"justification_recorded":true,"requested_by":"OP-01"}` |
| 13 | 2026-11-22T04:42:47+00:00 | REV-02 | STATUS_CHANGED | REF-2026-0007 | In Review -> Closed | `{"approval_id":1}` |
| 14 | 2026-11-22T04:42:47+00:00 | OP-02 | STATUS_CHANGED | REF-2026-0008 | New -> In Review | `{}` |
| 15 | 2026-11-22T04:42:47+00:00 | OP-01 | STATUS_CHANGED | REF-2026-0002 | New -> In Review | `{}` |
| 16 | 2026-11-22T04:42:47+00:00 | OP-01 | APPROVAL_REQUESTED | REF-2026-0002 | In Review -> Closed | `{"approval_id":2,"gate":"HITL"}` |
| 17 | 2026-11-22T04:42:48+00:00 | OP-01 | RAG_QUERY |  |  ->  | `{"abstained":false,"bm25_hits":7,"citations":["REF-2026-0007","SOP-05 \u00a72","REF-2026-0001"],"dense_hits":36,"final":3,"fused":36,"query_sha256":"2c9ffafab447"}` |
| 18 | 2026-11-22T04:42:49+00:00 | OP-01 | RAG_QUERY |  |  ->  | `{"abstained":true,"bm25_hits":0,"citations":[],"dense_hits":36,"final":0,"fused":36,"query_sha256":"a2589c2a330e"}` |
| 19 | 2026-11-22T04:42:49+00:00 | OP-01 | REQUEST_REFUSED |  |  ->  | `{"category":"causality assessment","input_sha256":"faa0e3a5582d","rule":"R2_CLINICAL_SCOPE"}` |
| 20 | 2026-11-22T04:42:49+00:00 | OP-01 | VALIDATION_FAILED | REF-2026-0999 |  ->  | `{"codes":["not_found"],"consecutive_failures":1,"fields":["_"],"tool":"update_status"}` |
| 21 | 2026-11-22T04:42:49+00:00 | OP-01 | VALIDATION_FAILED | REF-2026-0999 |  ->  | `{"codes":["not_found"],"consecutive_failures":2,"fields":["_"],"tool":"update_status"}` |
| 22 | 2026-11-22T04:42:49+00:00 | OP-01 | VALIDATION_FAILED | REF-2026-0999 |  ->  | `{"codes":["not_found"],"consecutive_failures":3,"fields":["_"],"tool":"update_status"}` |
| 23 | 2026-11-22T04:42:49+00:00 | OP-01 | CIRCUIT_OPEN |  |  ->  | `{"consecutive_failures":3,"signature_sha256":"54e0ccbec47bb537","threshold":2,"tool":"update_status"}` |

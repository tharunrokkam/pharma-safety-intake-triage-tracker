"""Pharma Safety Intake & Triage Tracker - Streamlit entry point.  Run:  streamlit run app.py"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from pharma_tracker.domain.enums import ApprovalStatus, ReportType, Status
from pharma_tracker.ui.common import DISCLAIMER, setup_page

service = setup_page("Pharma Safety Intake & Triage Tracker", "💊")
st.info(DISCLAIMER)

by_status = service.repo.count_by("status")
by_type = service.repo.count_by("report_type")
pending = len(service.repo.list_approvals(ApprovalStatus.PENDING))
c = st.columns(6)
c[0].metric("Total reports", sum(by_status.values()))
c[1].metric("New", by_status.get(Status.NEW.value, 0))
c[2].metric("In Review", by_status.get(Status.IN_REVIEW.value, 0))
c[3].metric("Closed", by_status.get(Status.CLOSED.value, 0))
c[4].metric("Adverse events", by_type.get(ReportType.SUSPECTED_ADVERSE_EVENT.value, 0))
c[5].metric("Pending HITL approvals", pending)

chain = service.repo.verify_audit_chain()
(st.success if chain.ok else st.error)(
    f"Audit hash chain: {'INTACT' if chain.ok else 'BROKEN at row ' + str(chain.first_bad_id)} "
    f"({chain.checked} events verified)")

st.markdown("""
**Pages**
- **New Report** - validated intake form (AE fields appear only for *Suspected Adverse Event*).
- **Dashboard** - tracker table with status / type filters and lifecycle actions.
- **Triage Approvals** - human-in-the-loop gate for *In Review -> Closed*.
- **Knowledge Agent** - deterministic LangGraph agent: routing, status commands and the 4-stage hybrid RAG with a pipeline inspector.
- **Audit Trail** - append-only, hash-chained event log plus the Claude Code governance-hook log.
""")

arch = Path(__file__).parent / "docs" / "architecture.png"
if arch.exists():
    with st.expander("Architecture (Plan Mode output)", expanded=False):
        st.image(str(arch), width="stretch")

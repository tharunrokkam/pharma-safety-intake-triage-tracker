"""Intake form - every submission goes through the LangGraph control plane (validator, breaker, audit)."""
from __future__ import annotations

from datetime import date

import streamlit as st

from pharma_tracker.domain.enums import ReporterType, ReportType
from pharma_tracker.ui.common import actor_id, apply_turn, setup_page, thread_id

service = setup_page("New Report", "📝")
st.caption("A reference id (REF-YYYY-NNNN) is generated automatically on successful submission. "
           "Do not enter personal identifiers - synthetic data only.")

errs: dict[str, str] = st.session_state.get("intake_errors", {})


def show_err(field: str) -> None:
    if field in errs:
        st.error(errs[field], icon="⚠️")


if st.session_state.get("intake_success"):
    st.success(st.session_state.pop("intake_success"))
if errs:
    st.error(f"Submission blocked - {len(errs)} field(s) need attention. See the messages under each field.")
    if "_" in errs:
        st.error(errs["_"])

report_type = st.radio("Report type *", [t.value for t in ReportType], horizontal=True, key="rt")
is_ae = report_type == ReportType.SUSPECTED_ADVERSE_EVENT.value

with st.form("intake", clear_on_submit=False):
    c1, c2 = st.columns(2)
    with c1:
        product = st.text_input("Product name *", placeholder="e.g. Fictivex 20mg")
        show_err("product_name")
        batch = st.text_input("Batch / Lot number *", placeholder="LOT-12345")
        show_err("batch_id")
    with c2:
        received = st.date_input("Date received *", value=date.today(), format="YYYY-MM-DD")
        show_err("date_received")
        reporter = st.selectbox("Reporter type *", [r.value for r in ReporterType], index=None,
                                placeholder="Select reporter type")
        show_err("reporter_type")
    description = st.text_area("Detailed description *", height=120,
                               placeholder="Factual description of the complaint / report (min 20 characters).")
    show_err("description")
    event_desc, onset = None, None
    if is_ae:
        st.markdown("**Adverse event extension** - describe the event only; no patient identifiers.")
        e1, e2 = st.columns([3, 1])
        with e1:
            event_desc = st.text_area("Event description *", height=90)
            show_err("event_description")
        with e2:
            onset = st.date_input("Event onset date *", value=None, format="YYYY-MM-DD")
            show_err("event_onset_date")
    submitted = st.form_submit_button("Submit report", type="primary")

if submitted:
    fields = {
        "report_type": report_type, "product_name": product, "batch_id": batch,
        "date_received": received.isoformat() if received else None, "reporter_type": reporter,
        "description": description,
    }
    if is_ae:
        fields["event_description"] = event_desc or None
        fields["event_onset_date"] = onset.isoformat() if onset else None
    fields = {k: v for k, v in fields.items() if v not in (None, "")}  # missing -> "is required"
    res = service.submit_report(thread_id(), fields, actor_id())
    apply_turn(res)
    if res.ok:
        st.session_state["intake_errors"] = {}
        st.session_state["intake_success"] = res.response.replace("**", "")
    elif res.halted:
        st.session_state["intake_errors"] = {"_": res.response}
    else:
        st.session_state["intake_errors"] = {e["field"]: e["message"] for e in res.errors}
    st.rerun()

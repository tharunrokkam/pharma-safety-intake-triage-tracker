"""Tracker dashboard: filter by status / type, inspect a report, run lifecycle actions."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from pharma_tracker.domain.enums import ReportType, Status
from pharma_tracker.domain.lifecycle import allowed_targets
from pharma_tracker.ui.common import actor_id, apply_turn, setup_page, thread_id

service = setup_page("Dashboard / Tracker", "📊")

f1, f2 = st.columns(2)
statuses = f1.multiselect("Filter by status", [s.value for s in Status], default=[])
types = f2.multiselect("Filter by report type", [t.value for t in ReportType], default=[])
rows = service.repo.list_reports(statuses or None, types or None)

m = st.columns(4)
m[0].metric("Shown", len(rows))
for i, s in enumerate(Status, start=1):
    m[i].metric(s.value, sum(r["status"] == s.value for r in rows))

if st.session_state.get("dash_msg"):
    kind, msg = st.session_state.pop("dash_msg")
    getattr(st, kind)(msg)

if not rows:
    st.info("No reports match the current filters. Create one on the **New Report** page or run "
            "`python scripts/seed_demo.py`.")
    st.stop()

df = pd.DataFrame(rows)[["ref_id", "report_type", "product_name", "batch_id", "date_received",
                         "reporter_type", "status", "created_by", "updated_at"]]
df.columns = ["Reference", "Type", "Product", "Batch/Lot", "Received", "Reporter", "Status", "Created by", "Updated (UTC)"]
event = st.dataframe(df, width="stretch", hide_index=True, on_select="rerun", selection_mode="single-row",
                     key="tracker")

sel = event.selection.rows if event and event.selection else []
if not sel:
    st.caption("Select a row to see details and available status actions.")
    st.stop()

rep = rows[sel[0]]
ref = rep["ref_id"]
st.subheader(f"{ref} - {rep['status']}")
d1, d2 = st.columns([2, 1])
with d1:
    st.markdown(f"**{rep['report_type']}** | {rep['product_name']} | `{rep['batch_id']}` | received {rep['date_received']} "
                f"| reporter: {rep['reporter_type']}")
    st.markdown(f"**Description:** {rep['description']}")
    if rep.get("event_description"):
        st.markdown(f"**Event:** {rep['event_description']}  \n**Onset:** {rep['event_onset_date']}")
    st.markdown("**Status history**")
    st.dataframe(pd.DataFrame(service.repo.list_transitions(ref))[
        ["ts_utc", "from_status", "to_status", "actor_id", "approval_id"]], hide_index=True, width="stretch")
with d2:
    st.markdown("**Lifecycle actions**")
    pending = [a for a in service.repo.list_approvals("PENDING") if a["ref_id"] == ref]
    targets = allowed_targets(rep["status"])
    if not targets:
        st.success("Closed - terminal state.")
    for tgt in targets:
        if tgt == Status.CLOSED:
            if pending:
                st.warning(f"Closure approval #{pending[0]['id']} is PENDING - record frozen until a reviewer decides "
                           "on the Triage Approvals page.")
                continue
            label = "Request closure (HITL approval)"
        else:
            label = f"Move to {tgt.value}"
        if st.button(label, key=f"btn-{ref}-{tgt.value}", type="primary"):
            res = service.update_status(thread_id(), ref, tgt.value, actor_id())
            apply_turn(res)
            st.session_state["dash_msg"] = ("success" if res.ok else "error", res.response.replace("**", ""))
            st.rerun()
    st.caption(f"Acting as **{actor_id()}**. Allowed next status: {', '.join(t.value for t in targets) or 'none'}.")

"""Human-in-the-loop gate: reviewers approve or reject In Review -> Closed requests."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from pharma_tracker.ui.common import actor_id, setup_page

service = setup_page("Triage Approvals (HITL)", "✅")
st.caption("Closing a report is frozen until a reviewer (REV-xx, different from the requester) records an explicit "
           "decision with a justification. The decision resumes the paused LangGraph workflow.")

if st.session_state.get("hitl_msg"):
    kind, msg = st.session_state.pop("hitl_msg")
    getattr(st, kind)(msg)

pending = service.repo.list_approvals("PENDING")
me = actor_id()
if not me.startswith("REV-"):
    st.warning(f"You are acting as **{me}** (operator). Switch the sidebar actor to a reviewer code (REV-xx) to decide.")

st.subheader(f"Pending approvals ({len(pending)})")
if not pending:
    st.info("No closure requests are waiting.")
for ap in pending:
    live = service.has_live_interrupt(ap.get("thread_id"))
    with st.expander(f"#{ap['id']} - {ap['ref_id']} - {ap['report_type']} - {ap['product_name']} ({ap['batch_id']})",
                     expanded=True):
        st.markdown(f"Requested by **{ap['requested_by']}** at {ap['requested_at']} UTC. Report status: **In Review** (frozen).")
        st.caption(f"LangGraph thread `{ap.get('thread_id')}` - "
                   + ("paused at `hitl_gate` (interrupt) - decision will resume it." if live else
                      "not in volatile memory (app restarted) - decision is recorded directly via the same tool."))
        just = st.text_area("Justification (required, min 10 characters)", key=f"just-{ap['id']}")
        b1, b2, _ = st.columns([1, 1, 4])
        for col, decision, label, kind in ((b1, "approve", "Approve closure", "primary"),
                                           (b2, "reject", "Reject", "secondary")):
            if col.button(label, key=f"{decision}-{ap['id']}", type=kind, disabled=not me.startswith("REV-")):
                res = service.decide_approval(ap["id"], me, decision, just)
                ok = res.result and res.result.get("ok")
                st.session_state["hitl_msg"] = ("success" if ok else "error", res.response.split("**Human-in-the-loop")[0]
                                                .replace("**", ""))
                st.rerun()

st.subheader("Decision history")
decided = [a for a in service.repo.list_approvals() if a["status"] != "PENDING"]
if decided:
    st.dataframe(pd.DataFrame(decided)[["id", "ref_id", "requested_by", "requested_at", "status", "reviewer_id",
                                        "justification", "decided_at"]], hide_index=True, width="stretch")
else:
    st.caption("No decisions recorded yet.")

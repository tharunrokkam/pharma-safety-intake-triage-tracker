"""Audit trail viewer: append-only, hash-chained events + Claude Code governance hook log."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from pharma_tracker.config import ROOT_DIR
from pharma_tracker.domain.enums import AuditAction
from pharma_tracker.ui.common import setup_page

service = setup_page("Audit Trail", "🧾")

chain = service.repo.verify_audit_chain()
if chain.ok:
    st.success(f"Hash chain INTACT - {chain.checked} events verified (SHA-256, append-only triggers active).")
else:
    st.error(f"Hash chain BROKEN at row {chain.first_bad_id}: {chain.reason}")

f1, f2 = st.columns(2)
actions = f1.multiselect("Action", [a.value for a in AuditAction])
ref = f2.text_input("Reference id", placeholder="REF-2026-0001").strip() or None
rows = service.repo.list_audit(ref_id=ref, actions=actions or None)
if rows:
    df = pd.DataFrame(rows)[["id", "ts_utc", "actor_id", "action", "ref_id", "from_status", "to_status",
                             "details_json", "row_hash"]]
    df["row_hash"] = df["row_hash"].str[:16] + "…"
    st.dataframe(df, hide_index=True, width="stretch")
    st.download_button("Export CSV", pd.DataFrame(rows).to_csv(index=False), "audit_trail.csv", "text/csv")
else:
    st.info("No audit events match.")

st.subheader("Governance hook log (Claude Code PostToolUse)")
st.caption("`.claude/settings.json` -> `.claude/hooks/audit_file_edit.py` -> `logs/claude_edit_audit.jsonl` "
           "(metadata only: timestamp, tool, path, hashes - never file content).")
hook_log = ROOT_DIR / "logs" / "claude_edit_audit.jsonl"
if hook_log.exists():
    lines = [json.loads(x) for x in hook_log.read_text(encoding="utf-8").splitlines() if x.strip()]
    st.caption(f"{len(lines)} file-edit events recorded.")
    st.dataframe(pd.DataFrame(lines[::-1]), hide_index=True, width="stretch")
else:
    st.caption("No hook events recorded yet.")

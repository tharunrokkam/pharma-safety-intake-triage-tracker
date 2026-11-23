"""Deterministic LangGraph agent chat with ReAct trace and 4-stage RAG pipeline inspector."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from pharma_tracker.config import RERANK_THRESHOLD
from pharma_tracker.ui.common import actor_id, apply_turn, setup_page, thread_id

service = setup_page("Knowledge Agent", "🔎")
st.caption("Deterministic router -> tools / hybrid RAG (BM25 + bi-encoder -> RRF k=60 -> cross-encoder >= 0.40). "
           "Answers are extractive quotes with citations - nothing is generated.")

EXAMPLES = [
    "any history of difficulty breathing with LOT-88392?",
    "what does the SOP say about closing a report?",
    "cracked or broken tablets complaints",
    "show REF-2026-0001",
    "should the patient stop taking Fictivex?",
]
cols = st.columns(len(EXAMPLES))
clicked = None
for c, ex in zip(cols, EXAMPLES):
    if c.button(ex, width="stretch"):
        clicked = ex

chat: list[dict] = st.session_state.setdefault("chat", [])


def hits_df(hits: list[dict], n: int = 10, threshold: bool = False) -> pd.DataFrame:
    df = pd.DataFrame(hits[:n])
    if df.empty:
        return df
    df = df[["rank", "citation", "score", "preview"]]
    if threshold:
        df["passes 0.40"] = df["score"] >= RERANK_THRESHOLD
    return df


def render_details(turn: dict) -> None:
    st.caption(f"Route: **{turn['route']}** - rule `{turn['route_rule']}` ({turn['route_reason']})")
    with st.expander("ReAct trace (Thought -> Action -> Observation)"):
        st.dataframe(pd.DataFrame(turn["trace"]), hide_index=True, width="stretch")
    r = turn.get("retrieval")
    if r:
        with st.expander("Pipeline inspector - 4-stage hybrid RAG", expanded=False):
            p = r["params"]
            st.caption(f"mode: {p['mode']} | chunks: {p['corpus_chunks']} | top-k {p['bm25_top_k']}/{p['dense_top_k']} | "
                       f"RRF k={p['rrf_k']} | threshold {p['rerank_threshold']} | max {p['rerank_max_k']} | "
                       f"timings ms: {r['timings_ms']}")
            a, b = st.columns(2)
            a.markdown(f"**Stage 1 - BM25** ({len(r['bm25'])} hits, k1=1.3 b=0.75)")
            a.dataframe(hits_df(r["bm25"]), hide_index=True, width="stretch")
            b.markdown(f"**Stage 2 - Bi-encoder cosine** ({len(r['dense'])} hits)")
            b.dataframe(hits_df(r["dense"]), hide_index=True, width="stretch")
            a.markdown(f"**Stage 3 - RRF fused pool** ({len(r['fused'])} candidates)")
            a.dataframe(hits_df(r["fused"]), hide_index=True, width="stretch")
            b.markdown(f"**Stage 4 - Cross-encoder rerank** -> {len(r['final'])} passed")
            b.dataframe(hits_df(r["reranked"], threshold=True), hide_index=True, width="stretch")


for turn in chat:
    with st.chat_message("user"):
        st.markdown(turn["user"])
    with st.chat_message("assistant"):
        st.markdown(turn["response"])
        render_details(turn)

prompt = st.chat_input("Ask about past reports / SOPs, or e.g. 'move REF-2026-0001 to in review'") or clicked
if prompt:
    res = service.chat(thread_id(), prompt, actor_id())
    apply_turn(res)
    chat.append({"user": prompt, "response": res.response, "route": res.route, "route_rule": res.route_rule,
                 "route_reason": res.route_reason, "trace": res.trace, "retrieval": res.retrieval})
    st.rerun()

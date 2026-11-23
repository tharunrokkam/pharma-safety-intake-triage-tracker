"""Shared Streamlit plumbing: cached AgentService, sidebar (pseudonymous actor), session thread ids."""
from __future__ import annotations

import os

import streamlit as st

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from ..agent.service import AgentService, TurnResult, new_thread_id  # noqa: E402
from ..config import OPERATORS, REVIEWERS  # noqa: E402

DISCLAIMER = ("Training prototype - **fictional data only**. Never assesses causality, recommends treatment, "
              "determines reportability or makes clinical/regulatory decisions.")


@st.cache_resource(show_spinner="Loading encoders and building the hybrid RAG index ...")
def get_service() -> AgentService:
    return AgentService(write_manifest=True)


def thread_id() -> str:
    if "thread_id" not in st.session_state:
        st.session_state["thread_id"] = new_thread_id()
    return st.session_state["thread_id"]


def apply_turn(res: TurnResult) -> None:
    """Interrupted (HITL) threads are handed to the approval workflow; continue on the next thread."""
    st.session_state["thread_id"] = res.next_thread_id


def actor_id() -> str:
    return st.session_state.get("actor_id", OPERATORS[0])


def setup_page(title: str, icon: str) -> AgentService:
    st.set_page_config(page_title=f"{title} - Pharma Intake Tracker", page_icon=icon, layout="wide")
    service = get_service()
    with st.sidebar:
        st.markdown("### Acting as")
        options = OPERATORS + REVIEWERS
        current = st.session_state.get("actor_id", OPERATORS[0])
        st.session_state["actor_id"] = st.selectbox(
            "Pseudonymous actor code", options, index=options.index(current),
            help="OP-xx = intake operator, REV-xx = triage reviewer. No real names are stored.")
        st.caption(f"Session thread: `{thread_id()}`")
        if st.button("Reset session", help="Start a new LangGraph thread (clears short-term memory and "
                                           "a tripped circuit breaker)."):
            st.session_state["thread_id"] = new_thread_id()
            st.session_state.pop("chat", None)
            st.rerun()
        st.divider()
        st.caption(f"RAG mode: {service.pipeline.mode}")
        st.caption(f"Indexed chunks: {service.pipeline.size}")
        st.divider()
        st.caption(DISCLAIMER)
    st.title(f"{icon} {title}")
    return service

"""AgentState - the short-term (volatile) memory checkpointed per thread by LangGraph InMemorySaver."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # turn input
    user_input: Optional[str]
    actor_id: str
    preset_call: Optional[dict[str, Any]]      # structured call from a UI form / button
    # routing
    route: str
    route_rule: str
    route_reason: str
    # tool execution
    tool_call: Optional[dict[str, Any]]        # {"tool": name, "args": {...}}
    prepared: Optional[dict[str, Any]]         # PreparedCall as dict
    result: Optional[dict[str, Any]]           # ToolResult as dict
    errors: list[dict[str, Any]]
    halted: bool
    # control plane memory that survives turns within a thread
    breaker: dict[str, Any]
    pending_approval: Optional[dict[str, Any]]
    # retrieval
    retrieval: Optional[dict[str, Any]]
    # ReAct trace (Thought -> Action -> Observation), rebuilt each turn
    react_trace: list[dict[str, str]]
    response: str
    messages: Annotated[list[dict[str, str]], operator.add]


TURN_DEFAULTS: dict[str, Any] = {
    "route": "", "route_rule": "", "route_reason": "", "tool_call": None, "prepared": None, "result": None,
    "errors": [], "halted": False, "pending_approval": None, "retrieval": None, "react_trace": [],
    "response": "",
}

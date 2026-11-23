"""Status lifecycle: New -> In Review -> Closed (Closed is terminal; close requires HITL)."""
from __future__ import annotations

from .enums import Status
from .errors import IllegalTransitionError

ALLOWED_TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.NEW: frozenset({Status.IN_REVIEW}),
    Status.IN_REVIEW: frozenset({Status.CLOSED}),
    Status.CLOSED: frozenset(),
}

HITL_REQUIRED: frozenset[tuple[Status, Status]] = frozenset({(Status.IN_REVIEW, Status.CLOSED)})


def allowed_targets(current: Status | str) -> list[Status]:
    return sorted(ALLOWED_TRANSITIONS[Status(current)], key=lambda s: list(Status).index(s))


def validate_transition(current: Status | str, target: Status | str) -> None:
    cur, tgt = Status(current), Status(target)
    if cur == tgt:
        raise IllegalTransitionError(f"Report is already '{cur}' - no transition performed.")
    if cur == Status.CLOSED:
        raise IllegalTransitionError("Closed reports are terminal and cannot change status.")
    if tgt not in ALLOWED_TRANSITIONS[cur]:
        legal = ", ".join(str(s) for s in allowed_targets(cur))
        raise IllegalTransitionError(
            f"Illegal transition '{cur}' -> '{tgt}'. From '{cur}' the only allowed next status is: {legal}."
        )


def requires_hitl(current: Status | str, target: Status | str) -> bool:
    return (Status(current), Status(target)) in HITL_REQUIRED

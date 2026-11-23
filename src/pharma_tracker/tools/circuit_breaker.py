"""Circuit breaker for repeated identical invalid tool calls (control plane step 5).

If the same tool is called with the same invalid arguments more than ``max_failures`` consecutive
times (default 2), the breaker opens and execution halts.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from ..config import BREAKER_MAX_CONSECUTIVE_FAILURES


def call_signature(tool_name: str, args: dict[str, Any]) -> str:
    canonical = json.dumps({"tool": tool_name, "args": args}, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class CircuitBreaker:
    max_failures: int = BREAKER_MAX_CONSECUTIVE_FAILURES
    last_signature: str | None = None
    consecutive_failures: int = 0
    is_open: bool = False

    def record_failure(self, signature: str) -> bool:
        """Register an invalid call; returns True when this call trips the breaker."""
        if signature == self.last_signature:
            self.consecutive_failures += 1
        else:
            self.last_signature = signature
            self.consecutive_failures = 1
        if self.consecutive_failures > self.max_failures:
            self.is_open = True
        return self.is_open

    def record_success(self) -> None:
        self.last_signature = None
        self.consecutive_failures = 0

    def reset(self) -> None:
        self.record_success()
        self.is_open = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CircuitBreaker":
        return cls(**data) if data else cls()


HALT_MESSAGE = (
    "Execution halted: the same tool was called with the same invalid arguments more than "
    f"{BREAKER_MAX_CONSECUTIVE_FAILURES} consecutive times (circuit breaker OPEN). "
    "Start a new session (sidebar -> 'Reset session') or correct the input."
)

"""Tool interrupt events — typed tool interaction events."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ToolEventKind(StrEnum):
    CALL = "tool_call"
    SUCCESS = "tool_success"
    ERROR = "tool_error"
    TIMEOUT = "tool_timeout"


@dataclass
class ToolEvent:
    """Typed tool interaction event."""

    event_id: str
    timestamp: float
    kind: ToolEventKind
    tool_name: str
    arguments: dict[str, Any]
    result: str | None
    error: str | None
    latency_ms: float
    normalized: dict[str, Any] | None

    @classmethod
    def create(
        cls,
        kind: ToolEventKind,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        result: str | None = None,
        error: str | None = None,
        latency_ms: float = 0.0,
        normalized: dict[str, Any] | None = None,
    ) -> ToolEvent:
        return cls(
            event_id=f"{int(time.time() * 1000):012x}-{uuid.uuid4().hex[:12]}",
            timestamp=time.time(),
            kind=kind,
            tool_name=tool_name,
            arguments=arguments or {},
            result=result,
            error=error,
            latency_ms=latency_ms,
            normalized=normalized,
        )

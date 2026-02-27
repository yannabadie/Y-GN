"""Session & EventLog — ground truth for an execution session."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from ..evidence import EvidencePack


@dataclass
class SessionEvent:
    """Typed event in the session timeline."""

    event_id: str
    timestamp: float
    kind: str
    data: dict[str, Any]
    token_estimate: int


class EventLog:
    """Append-only ordered log of SessionEvents."""

    def __init__(self) -> None:
        self.events: list[SessionEvent] = []

    def append(
        self, kind: str, data: dict[str, Any], token_estimate: int = 0
    ) -> SessionEvent:
        event = SessionEvent(
            event_id=f"{int(time.time() * 1000):012x}-{uuid.uuid4().hex[:12]}",
            timestamp=time.time(),
            kind=kind,
            data=data,
            token_estimate=token_estimate,
        )
        self.events.append(event)
        return event

    def filter(self, kinds: list[str]) -> list[SessionEvent]:
        return [e for e in self.events if e.kind in kinds]

    def total_tokens(self) -> int:
        return sum(e.token_estimate for e in self.events)

    def since(self, timestamp: float) -> list[SessionEvent]:
        return [e for e in self.events if e.timestamp >= timestamp]


# Map SessionEvent kinds to EvidenceKind values
_KIND_TO_EVIDENCE: dict[str, str] = {
    "user_input": "input",
    "memory_hit": "source",
    "tool_call": "tool_call",
    "tool_success": "output",
    "tool_error": "error",
    "tool_timeout": "error",
    "guard_decision": "decision",
    "phase_result": "output",
    "artifact_stored": "output",
}


class Session:
    """Wraps EventLog + EvidencePack. Single source of truth per execution."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.event_log = EventLog()
        self.evidence = EvidencePack(session_id=self.session_id)

    def record(
        self, kind: str, data: dict[str, Any], token_estimate: int = 0
    ) -> SessionEvent:
        event = self.event_log.append(kind, data, token_estimate)
        evidence_kind = _KIND_TO_EVIDENCE.get(kind, "output")
        self.evidence.add(kind, evidence_kind, data)
        return event

    def to_evidence_pack(self) -> EvidencePack:
        return self.evidence

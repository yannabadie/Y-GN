"""Event Sourcing for FSM — append-only event log with replay capability."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .fsm import Phase


@dataclass
class FSMEvent:
    """A single FSM state-transition event."""

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)
    from_phase: str = ""
    to_phase: str = ""
    trigger: str = ""  # "user_input", "phase_complete", "retry", etc.
    metadata: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""


class EventStore(ABC):
    """Abstract event store for FSM events."""

    @abstractmethod
    def append(self, event: FSMEvent) -> None:
        """Append an event to the store."""

    @abstractmethod
    def events(self, session_id: str | None = None) -> list[FSMEvent]:
        """Retrieve events, optionally filtered by session."""

    @abstractmethod
    def replay(self, target_event_id: str | None = None) -> Phase:
        """Replay events up to *target_event_id* and return the final phase."""

    @abstractmethod
    def snapshot(self, session_id: str) -> dict[str, Any]:
        """Return a snapshot of the current state for the given session."""

    @abstractmethod
    def clear(self, session_id: str | None = None) -> int:
        """Remove events (optionally for a specific session). Returns count removed."""


class InMemoryEventStore(EventStore):
    """In-memory implementation of :class:`EventStore`."""

    def __init__(self) -> None:
        self._events: list[FSMEvent] = []

    def append(self, event: FSMEvent) -> None:
        self._events.append(event)

    def events(self, session_id: str | None = None) -> list[FSMEvent]:
        if session_id is None:
            return list(self._events)
        return [e for e in self._events if e.session_id == session_id]

    def replay(self, target_event_id: str | None = None) -> Phase:
        """Walk through events, applying transitions, and return the final phase.

        If *target_event_id* is given, stop after that event.
        """
        phase = Phase.IDLE
        for event in self._events:
            phase = Phase(event.to_phase)
            if target_event_id is not None and event.event_id == target_event_id:
                break
        return phase

    def snapshot(self, session_id: str) -> dict[str, Any]:
        session_events = self.events(session_id=session_id)
        if not session_events:
            return {
                "session_id": session_id,
                "current_phase": Phase.IDLE.value,
                "event_count": 0,
                "last_event_timestamp": None,
            }
        last = session_events[-1]
        return {
            "session_id": session_id,
            "current_phase": last.to_phase,
            "event_count": len(session_events),
            "last_event_timestamp": last.timestamp,
        }

    def clear(self, session_id: str | None = None) -> int:
        if session_id is None:
            count = len(self._events)
            self._events.clear()
            return count
        original = len(self._events)
        self._events = [e for e in self._events if e.session_id != session_id]
        return original - len(self._events)

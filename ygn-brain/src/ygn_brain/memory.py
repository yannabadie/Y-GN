"""Memory service interface — store, recall, forget."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum


class MemoryCategory(StrEnum):
    CORE = "core"
    DAILY = "daily"
    CONVERSATION = "conversation"
    CUSTOM = "custom"


@dataclass
class MemoryEntry:
    """A single memory record."""

    key: str
    content: str
    category: MemoryCategory
    timestamp: float = field(default_factory=time.time)
    session_id: str | None = None


class MemoryService(ABC):
    """Abstract interface for memory backends."""

    @abstractmethod
    def store(
        self,
        key: str,
        content: str,
        category: MemoryCategory,
        session_id: str | None = None,
    ) -> None:
        """Persist a memory entry."""

    @abstractmethod
    def recall(
        self,
        query: str,
        limit: int = 5,
        session_id: str | None = None,
    ) -> list[MemoryEntry]:
        """Retrieve memories matching the query."""

    @abstractmethod
    def forget(self, key: str) -> bool:
        """Remove a memory entry by key. Returns True if found and removed."""


class InMemoryBackend(MemoryService):
    """Dict-based in-memory implementation (for testing and development)."""

    def __init__(self) -> None:
        self._store: dict[str, MemoryEntry] = {}

    def store(
        self,
        key: str,
        content: str,
        category: MemoryCategory,
        session_id: str | None = None,
    ) -> None:
        self._store[key] = MemoryEntry(
            key=key,
            content=content,
            category=category,
            session_id=session_id,
        )

    def recall(
        self,
        query: str,
        limit: int = 5,
        session_id: str | None = None,
    ) -> list[MemoryEntry]:
        """Word-overlap matching recall (production would use embeddings)."""
        query_words = {w for w in query.lower().split() if len(w) >= 3}
        matches: list[MemoryEntry] = []
        for entry in self._store.values():
            # Filter by session if specified
            if session_id is not None and entry.session_id != session_id:
                continue
            # Word-overlap match on content or key
            entry_text = f"{entry.key} {entry.content}".lower()
            if any(word in entry_text for word in query_words):
                matches.append(entry)
        # Sort by timestamp descending (most recent first)
        matches.sort(key=lambda e: e.timestamp, reverse=True)
        return matches[:limit]

    def forget(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

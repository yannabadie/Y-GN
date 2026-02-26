"""Tiered memory service — hot (TTL cache), warm (indexed), cold (persistent)."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum

from .embeddings import EmbeddingService
from .entity_extraction import EntityExtractor
from .memory import MemoryCategory, MemoryEntry, MemoryService


class MemoryTier(StrEnum):
    """The three memory tiers."""

    HOT = "hot"  # Recent, fast, TTL-based cache
    WARM = "warm"  # Temporal index + tags
    COLD = "cold"  # Long-term persistent


# ---------------------------------------------------------------------------
# Tier entry types
# ---------------------------------------------------------------------------


@dataclass
class HotEntry:
    """A hot-tier entry with a TTL expiry timestamp."""

    key: str
    content: str
    category: MemoryCategory
    session_id: str | None
    expires_at: float  # time.time() + ttl
    tags: list[str] = field(default_factory=list)


@dataclass
class WarmEntry:
    """A warm-tier entry with tag-based indexing."""

    key: str
    content: str
    category: MemoryCategory
    session_id: str | None
    timestamp: float
    tags: list[str] = field(default_factory=list)


@dataclass
class ColdEntry:
    """A cold-tier entry with relations for future knowledge-graph support."""

    key: str
    content: str
    category: MemoryCategory
    session_id: str | None
    timestamp: float
    tags: list[str] = field(default_factory=list)
    relations: list[str] = field(default_factory=list)  # keys of related entries
    embedding: list[float] | None = None


# ---------------------------------------------------------------------------
# TieredMemoryService
# ---------------------------------------------------------------------------


class TieredMemoryService(MemoryService):
    """3-tier memory: hot (cache) -> warm (indexed) -> cold (persistent).

    Hot entries expire after ``hot_ttl_seconds`` and are evicted on access or
    explicit ``decay()`` calls.  Warm entries are promoted to cold during decay
    when they exceed ``warm_max_age_seconds``.
    """

    def __init__(
        self,
        hot_ttl_seconds: float = 300.0,
        warm_max_age_seconds: float = 3600.0,
        embedding_service: EmbeddingService | None = None,
        entity_extractor: EntityExtractor | None = None,
    ) -> None:
        self._hot: dict[str, HotEntry] = {}
        self._warm: dict[str, WarmEntry] = {}
        self._cold: dict[str, ColdEntry] = {}
        self._hot_ttl = hot_ttl_seconds
        self._warm_max_age = warm_max_age_seconds
        self._embedding_service = embedding_service
        self._entity_extractor = entity_extractor
        self._relation_index: dict[str, set[str]] = defaultdict(set)

    # ----- MemoryService interface -----------------------------------------

    def store(  # noqa: PLR0913
        self,
        key: str,
        content: str,
        category: MemoryCategory,
        session_id: str | None = None,
        *,
        tags: list[str] | None = None,
        tier: MemoryTier = MemoryTier.HOT,
    ) -> None:
        """Store an entry in the specified tier."""
        resolved_tags = tags or []
        now = time.time()

        if tier == MemoryTier.HOT:
            self._hot[key] = HotEntry(
                key=key,
                content=content,
                category=category,
                session_id=session_id,
                expires_at=now + self._hot_ttl,
                tags=resolved_tags,
            )
        elif tier == MemoryTier.WARM:
            self._warm[key] = WarmEntry(
                key=key,
                content=content,
                category=category,
                session_id=session_id,
                timestamp=now,
                tags=resolved_tags,
            )
        else:  # COLD
            relations: list[str] = []
            if self._entity_extractor is not None:
                relations = self._entity_extractor.extract(content)
            self._cold[key] = ColdEntry(
                key=key,
                content=content,
                category=category,
                session_id=session_id,
                timestamp=now,
                tags=resolved_tags,
                relations=relations,
            )
            for entity in relations:
                self._relation_index[entity].add(key)

    def recall(
        self,
        query: str,
        limit: int = 5,
        session_id: str | None = None,
        *,
        tier: MemoryTier | None = None,
        tags: list[str] | None = None,
    ) -> list[MemoryEntry]:
        """Search across tiers (hot first, then warm, then cold).

        If *tier* is specified, only that tier is searched.
        If *tags* is specified, entries must contain at least one matching tag.
        TTL eviction is applied on hot-tier entries during recall.
        """
        now = time.time()
        results: list[MemoryEntry] = []
        query_words = {w for w in query.lower().split() if len(w) >= 3}

        # --- hot ---
        if tier is None or tier == MemoryTier.HOT:
            expired_keys: list[str] = []
            for key, entry in self._hot.items():
                if entry.expires_at <= now:
                    expired_keys.append(key)
                    continue
                if not self._matches(
                    entry.content,
                    entry.key,
                    query_words,
                    session_id,
                    entry.session_id,
                    tags,
                    entry.tags,
                ):
                    continue
                results.append(
                    self._to_memory_entry(
                        entry.key, entry.content, entry.category, entry.session_id
                    )
                )
            for k in expired_keys:
                del self._hot[k]

        # --- warm ---
        if tier is None or tier == MemoryTier.WARM:
            for warm_entry in self._warm.values():
                if not self._matches(
                    warm_entry.content,
                    warm_entry.key,
                    query_words,
                    session_id,
                    warm_entry.session_id,
                    tags,
                    warm_entry.tags,
                ):
                    continue
                results.append(
                    self._to_memory_entry(
                        warm_entry.key,
                        warm_entry.content,
                        warm_entry.category,
                        warm_entry.session_id,
                        timestamp=warm_entry.timestamp,
                    )
                )

        # --- cold ---
        if tier is None or tier == MemoryTier.COLD:
            for cold_entry in self._cold.values():
                if not self._matches(
                    cold_entry.content,
                    cold_entry.key,
                    query_words,
                    session_id,
                    cold_entry.session_id,
                    tags,
                    cold_entry.tags,
                ):
                    continue
                results.append(
                    self._to_memory_entry(
                        cold_entry.key,
                        cold_entry.content,
                        cold_entry.category,
                        cold_entry.session_id,
                        timestamp=cold_entry.timestamp,
                    )
                )

        # Most recent first
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def recall_by_relation(self, entity: str) -> list[MemoryEntry]:
        """Return cold-tier entries that mention *entity* in their relations."""
        keys = self._relation_index.get(entity, set())
        results: list[MemoryEntry] = []
        for k in keys:
            entry = self._cold.get(k)
            if entry is not None:
                results.append(
                    self._to_memory_entry(
                        entry.key,
                        entry.content,
                        entry.category,
                        entry.session_id,
                        timestamp=entry.timestamp,
                    )
                )
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results

    def recall_multihop(self, query: str, hops: int = 2) -> list[MemoryEntry]:
        """Multi-hop recall: follow relation chains up to *hops* levels deep."""
        seen_keys: set[str] = set()
        # Seed: entities to explore at the current hop
        frontier: set[str] = {query}

        for _ in range(hops):
            next_frontier: set[str] = set()
            for entity in frontier:
                for key in self._relation_index.get(entity, set()):
                    if key not in seen_keys:
                        seen_keys.add(key)
                        cold_entry = self._cold.get(key)
                        if cold_entry is not None:
                            # Add this entry's relations to the next frontier
                            next_frontier.update(cold_entry.relations)
            frontier = next_frontier - frontier  # avoid re-exploring same entities

        results: list[MemoryEntry] = []
        for k in seen_keys:
            entry = self._cold.get(k)
            if entry is not None:
                results.append(
                    self._to_memory_entry(
                        entry.key,
                        entry.content,
                        entry.category,
                        entry.session_id,
                        timestamp=entry.timestamp,
                    )
                )
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results

    def forget(self, key: str) -> bool:
        """Remove an entry from all tiers. Returns True if found in any tier."""
        found = False
        if key in self._hot:
            del self._hot[key]
            found = True
        if key in self._warm:
            del self._warm[key]
            found = True
        if key in self._cold:
            del self._cold[key]
            found = True
        return found

    # ----- Tier management -------------------------------------------------

    def promote(self, key: str, target_tier: MemoryTier) -> bool:
        """Move an entry to *target_tier*.

        Searches all tiers for the key and moves it.  Returns True if the key
        was found and moved, False otherwise.
        """
        source = self._find_entry(key)
        if source is None:
            return False

        content, category, session_id, tags = source

        # Remove from all tiers first
        self._hot.pop(key, None)
        self._warm.pop(key, None)
        self._cold.pop(key, None)

        # Store in target tier
        self.store(key, content, category, session_id, tags=tags, tier=target_tier)
        return True

    def decay(self) -> tuple[int, int]:
        """Run a decay pass.

        1. Evict expired hot-tier entries.
        2. Promote warm-tier entries older than ``warm_max_age_seconds`` to cold.

        Returns ``(evicted_hot, promoted_to_cold)`` counts.
        """
        now = time.time()

        # Evict expired hot entries
        expired_hot = [k for k, e in self._hot.items() if e.expires_at <= now]
        for k in expired_hot:
            del self._hot[k]

        # Promote aged warm entries to cold
        aged_warm = [k for k, e in self._warm.items() if (now - e.timestamp) >= self._warm_max_age]
        for k in aged_warm:
            entry = self._warm.pop(k)
            self._cold[k] = ColdEntry(
                key=entry.key,
                content=entry.content,
                category=entry.category,
                session_id=entry.session_id,
                timestamp=entry.timestamp,
                tags=entry.tags,
            )

        return (len(expired_hot), len(aged_warm))

    # ----- Internals -------------------------------------------------------

    @staticmethod
    def _matches(
        content: str,
        key: str,
        query_words: set[str],
        session_filter: str | None,
        entry_session: str | None,
        tag_filter: list[str] | None,
        entry_tags: list[str],
    ) -> bool:
        """Check if an entry matches search criteria."""
        if session_filter is not None and entry_session != session_filter:
            return False
        if tag_filter:
            tag_set = set(tag_filter)
            if not tag_set.intersection(entry_tags):
                return False
        if not query_words:
            return True
        entry_text = f"{key} {content}".lower()
        return any(word in entry_text for word in query_words)

    @staticmethod
    def _to_memory_entry(
        key: str,
        content: str,
        category: MemoryCategory,
        session_id: str | None,
        *,
        timestamp: float | None = None,
    ) -> MemoryEntry:
        return MemoryEntry(
            key=key,
            content=content,
            category=category,
            session_id=session_id,
            timestamp=timestamp if timestamp is not None else time.time(),
        )

    def _find_entry(self, key: str) -> tuple[str, MemoryCategory, str | None, list[str]] | None:
        """Locate entry across tiers, returning (content, category, session_id, tags)."""
        if key in self._hot:
            h = self._hot[key]
            return (h.content, h.category, h.session_id, h.tags)
        if key in self._warm:
            w = self._warm[key]
            return (w.content, w.category, w.session_id, w.tags)
        if key in self._cold:
            c = self._cold[key]
            return (c.content, c.category, c.session_id, c.tags)
        return None

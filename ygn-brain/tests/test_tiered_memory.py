"""Tests for tiered memory — hot TTL, warm tags, cold persistence, cross-tier recall."""

import time

from ygn_brain.memory import MemoryCategory
from ygn_brain.tiered_memory import MemoryTier, TieredMemoryService


def test_hot_tier_storage_and_ttl_expiry():
    """Hot entries expire after the configured TTL."""
    mem = TieredMemoryService(hot_ttl_seconds=0.1)  # 100ms TTL
    mem.store("greeting", "hello world", MemoryCategory.CONVERSATION)

    # Should find it immediately
    results = mem.recall("hello")
    assert len(results) == 1
    assert results[0].key == "greeting"

    # Wait for TTL to expire
    time.sleep(0.15)
    results = mem.recall("hello")
    assert len(results) == 0


def test_warm_tier_with_tag_based_retrieval():
    """Warm entries can be filtered by tags."""
    mem = TieredMemoryService()
    mem.store(
        "arch-decision",
        "use microservices architecture",
        MemoryCategory.CORE,
        tags=["architecture", "design"],
        tier=MemoryTier.WARM,
    )
    mem.store(
        "deploy-note",
        "deploy to kubernetes cluster",
        MemoryCategory.DAILY,
        tags=["ops", "deploy"],
        tier=MemoryTier.WARM,
    )

    # Tag-filtered recall
    results = mem.recall("architecture deploy", tags=["architecture"])
    assert len(results) == 1
    assert results[0].key == "arch-decision"

    # Without tag filter, both match
    results = mem.recall("architecture deploy", limit=10)
    assert len(results) == 2


def test_cold_tier_persistence():
    """Cold tier entries persist and are searchable."""
    mem = TieredMemoryService()
    mem.store(
        "old-fact",
        "the earth orbits the sun",
        MemoryCategory.CORE,
        tags=["science"],
        tier=MemoryTier.COLD,
    )

    results = mem.recall("earth orbits", tier=MemoryTier.COLD)
    assert len(results) == 1
    assert results[0].key == "old-fact"
    assert results[0].content == "the earth orbits the sun"


def test_cross_tier_recall():
    """Recall searches all tiers when no specific tier is given."""
    mem = TieredMemoryService(hot_ttl_seconds=300.0)
    mem.store("hot-item", "recent topic alpha", MemoryCategory.CONVERSATION,
              tier=MemoryTier.HOT)
    mem.store("warm-item", "indexed topic alpha", MemoryCategory.CORE,
              tags=["test"], tier=MemoryTier.WARM)
    mem.store("cold-item", "persistent topic alpha", MemoryCategory.CORE,
              tags=["test"], tier=MemoryTier.COLD)

    results = mem.recall("topic alpha", limit=10)
    assert len(results) == 3
    keys = {r.key for r in results}
    assert keys == {"hot-item", "warm-item", "cold-item"}


def test_decay_evicts_hot_and_promotes_warm():
    """Decay evicts expired hot entries and promotes aged warm entries to cold."""
    mem = TieredMemoryService(hot_ttl_seconds=0.05, warm_max_age_seconds=0.05)

    mem.store("hot-temp", "ephemeral data", MemoryCategory.CONVERSATION,
              tier=MemoryTier.HOT)
    mem.store("warm-aging", "aging indexed data", MemoryCategory.CORE,
              tags=["aging"], tier=MemoryTier.WARM)

    # Wait for both TTL and warm age to expire
    time.sleep(0.1)

    evicted, promoted = mem.decay()
    assert evicted == 1  # hot-temp was evicted
    assert promoted == 1  # warm-aging was promoted to cold

    # hot-temp should be gone entirely
    assert mem.recall("ephemeral", limit=10) == []

    # warm-aging should now be in cold tier
    results = mem.recall("aging indexed", tier=MemoryTier.COLD)
    assert len(results) == 1
    assert results[0].key == "warm-aging"

    # warm tier should be empty for that key
    results = mem.recall("aging indexed", tier=MemoryTier.WARM)
    assert len(results) == 0


def test_promote_between_tiers():
    """Promote moves an entry to the target tier."""
    mem = TieredMemoryService(hot_ttl_seconds=300.0)
    mem.store("fact", "important fact to remember", MemoryCategory.CORE,
              tier=MemoryTier.HOT)

    # Promote from hot to cold
    assert mem.promote("fact", MemoryTier.COLD) is True

    # Should not be in hot
    results = mem.recall("important fact", tier=MemoryTier.HOT)
    assert len(results) == 0

    # Should be in cold
    results = mem.recall("important fact", tier=MemoryTier.COLD)
    assert len(results) == 1
    assert results[0].key == "fact"

    # Promote nonexistent key returns False
    assert mem.promote("nonexistent", MemoryTier.WARM) is False


def test_forget_removes_from_all_tiers():
    """Forget removes an entry regardless of which tier it is in."""
    mem = TieredMemoryService(hot_ttl_seconds=300.0)
    mem.store("a", "hot content", MemoryCategory.CONVERSATION, tier=MemoryTier.HOT)
    mem.store("b", "warm content", MemoryCategory.CORE, tags=["t"], tier=MemoryTier.WARM)
    mem.store("c", "cold content", MemoryCategory.CORE, tags=["t"], tier=MemoryTier.COLD)

    assert mem.forget("a") is True
    assert mem.forget("b") is True
    assert mem.forget("c") is True
    assert mem.forget("a") is False  # already gone

    results = mem.recall("content", limit=10)
    assert len(results) == 0


def test_session_filtering_across_tiers():
    """Session filtering works across all tiers."""
    mem = TieredMemoryService(hot_ttl_seconds=300.0)
    mem.store("x", "session one data", MemoryCategory.CONVERSATION,
              session_id="s1", tier=MemoryTier.HOT)
    mem.store("y", "session two data", MemoryCategory.CONVERSATION,
              session_id="s2", tier=MemoryTier.WARM)

    results = mem.recall("data", session_id="s1", limit=10)
    assert len(results) == 1
    assert results[0].session_id == "s1"

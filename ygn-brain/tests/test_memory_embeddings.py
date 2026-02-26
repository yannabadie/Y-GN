"""Tests for semantic memory recall with embeddings."""

from ygn_brain.embeddings import StubEmbeddingService
from ygn_brain.memory import MemoryCategory
from ygn_brain.tiered_memory import TieredMemoryService, MemoryTier


def test_tiered_memory_accepts_embedding_service():
    svc = StubEmbeddingService(dimension=4)
    mem = TieredMemoryService(embedding_service=svc)
    assert mem._embedding_service is svc


def test_tiered_memory_works_without_embedding_service():
    """Backward compat: no embedding service, word-overlap search."""
    mem = TieredMemoryService()
    mem.store("k1", "the cat sat on the mat", MemoryCategory.CORE, "s1")
    results = mem.recall("cat", limit=5)
    assert len(results) >= 1


def test_cold_entry_has_embedding_field():
    from ygn_brain.tiered_memory import ColdEntry

    entry = ColdEntry(
        key="k1",
        content="test",
        category=MemoryCategory.CORE,
        session_id="s1",
        timestamp=1.0,
        embedding=[0.1, 0.2, 0.3],
    )
    assert entry.embedding == [0.1, 0.2, 0.3]


def test_cold_entry_embedding_defaults_none():
    from ygn_brain.tiered_memory import ColdEntry

    entry = ColdEntry(
        key="k1",
        content="test",
        category=MemoryCategory.CORE,
        session_id="s1",
        timestamp=1.0,
    )
    assert entry.embedding is None

"""Tests for Temporal Knowledge Graph features."""

from ygn_brain.entity_extraction import RegexEntityExtractor
from ygn_brain.memory import MemoryCategory
from ygn_brain.tiered_memory import MemoryTier, TieredMemoryService


def test_cold_store_populates_relations():
    ext = RegexEntityExtractor()
    mem = TieredMemoryService(entity_extractor=ext)
    mem.store(
        "k1",
        "Call def process_data in /src/pipeline.py",
        MemoryCategory.CORE,
        "s1",
        tier=MemoryTier.COLD,
    )
    cold = mem._cold["k1"]
    assert len(cold.relations) > 0
    assert "process_data" in cold.relations


def test_recall_by_relation():
    ext = RegexEntityExtractor()
    mem = TieredMemoryService(entity_extractor=ext)
    mem.store(
        "k1",
        "def process_data handles input",
        MemoryCategory.CORE,
        "s1",
        tier=MemoryTier.COLD,
    )
    mem.store(
        "k2",
        "def validate_data checks input",
        MemoryCategory.CORE,
        "s1",
        tier=MemoryTier.COLD,
    )

    results = mem.recall_by_relation("process_data")
    assert len(results) >= 1
    assert any(r.key == "k1" for r in results)


def test_recall_multihop():
    ext = RegexEntityExtractor()
    mem = TieredMemoryService(entity_extractor=ext)
    # k1 mentions both def process_data and def validate_data -> links to k2
    mem.store(
        "k1",
        "def process_data calls def validate_data",
        MemoryCategory.CORE,
        "s1",
        tier=MemoryTier.COLD,
    )
    mem.store(
        "k2",
        "def validate_data checks schema",
        MemoryCategory.CORE,
        "s1",
        tier=MemoryTier.COLD,
    )

    results = mem.recall_multihop("process_data", hops=2)
    keys = [r.key for r in results]
    assert "k1" in keys
    assert "k2" in keys


def test_backward_compat_no_extractor():
    mem = TieredMemoryService()
    mem.store(
        "k1", "def process_data", MemoryCategory.CORE, "s1", tier=MemoryTier.COLD
    )
    cold = mem._cold["k1"]
    assert cold.relations == []


def test_relation_index_updated():
    ext = RegexEntityExtractor()
    mem = TieredMemoryService(entity_extractor=ext)
    mem.store(
        "k1", "def process_data", MemoryCategory.CORE, "s1", tier=MemoryTier.COLD
    )
    assert "process_data" in mem._relation_index
    assert "k1" in mem._relation_index["process_data"]

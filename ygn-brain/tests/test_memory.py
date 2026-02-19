"""Tests for memory module — store, recall, forget."""

from ygn_brain.memory import InMemoryBackend, MemoryCategory


def test_store_and_recall():
    mem = InMemoryBackend()
    mem.store("greeting", "Hello world", MemoryCategory.CONVERSATION)
    results = mem.recall("hello")
    assert len(results) == 1
    assert results[0].key == "greeting"
    assert results[0].content == "Hello world"


def test_forget_returns_true_for_existing():
    mem = InMemoryBackend()
    mem.store("temp", "temporary data", MemoryCategory.DAILY)
    assert mem.forget("temp") is True
    assert mem.forget("temp") is False  # already removed


def test_recall_filters_by_session():
    mem = InMemoryBackend()
    mem.store("a", "session one data", MemoryCategory.CONVERSATION, session_id="s1")
    mem.store("b", "session two data", MemoryCategory.CONVERSATION, session_id="s2")
    results = mem.recall("data", session_id="s1")
    assert len(results) == 1
    assert results[0].session_id == "s1"


def test_recall_respects_limit():
    mem = InMemoryBackend()
    for i in range(10):
        mem.store(f"item_{i}", f"content about topic {i}", MemoryCategory.CORE)
    results = mem.recall("topic", limit=3)
    assert len(results) == 3

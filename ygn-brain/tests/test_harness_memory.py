"""Tests for harness memory store."""

from ygn_brain.harness.memory_store import HarnessMemoryStore
from ygn_brain.harness.types import Candidate, Feedback


def test_store_and_recall_pattern():
    store = HarnessMemoryStore()
    c = Candidate(
        id="c1",
        provider="codex",
        model="m",
        prompt="solve X",
        output="answer",
        latency_ms=100,
        token_count=10,
    )
    f = Feedback(passed=True, score=0.9, diagnostics="ok")
    store.store_pattern("solve math", c, f)

    patterns = store.recall_patterns("solve math")
    assert len(patterns) >= 1
    assert patterns[0]["provider"] == "codex"
    assert patterns[0]["score"] == 0.9


def test_recall_empty():
    store = HarnessMemoryStore()
    patterns = store.recall_patterns("unknown task")
    assert patterns == []

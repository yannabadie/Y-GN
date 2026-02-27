"""Tests for context compiler processors."""

import tempfile
from pathlib import Path

from ygn_brain.context_compiler.artifact_store import SqliteArtifactStore
from ygn_brain.context_compiler.processors import (
    ArtifactAttacher,
    Compactor,
    ContextCompiler,
    HistorySelector,
    MemoryPreloader,
)
from ygn_brain.context_compiler.session import Session
from ygn_brain.context_compiler.working_context import WorkingContext
from ygn_brain.memory import InMemoryBackend


def _make_session_with_history(n_turns: int) -> Session:
    session = Session()
    for i in range(n_turns):
        role = "user" if i % 2 == 0 else "assistant"
        session.record(
            "user_input" if role == "user" else "phase_result",
            {"role": role, "content": f"Message {i}"},
            token_estimate=20,
        )
    return session


def test_history_selector_keeps_first_and_last():
    session = _make_session_with_history(20)
    ctx = WorkingContext(
        system_prompt="test", history=[], memory_hits=[], artifact_refs=[],
        tool_results=[], token_count=0, budget=500,
    )
    selector = HistorySelector(keep_first=2, keep_last=3)
    result = selector.process(session, ctx, budget=500)
    # Should have 5 entries: first 2 + last 3
    assert len(result.history) == 5
    assert result.history[0]["content"] == "Message 0"
    assert result.history[1]["content"] == "Message 1"
    assert result.history[-1]["content"] == "Message 19"


def test_compactor_merges_consecutive():
    session = Session()
    ctx = WorkingContext(
        system_prompt="test",
        history=[
            {"role": "user", "content": "  Hello  "},
            {"role": "user", "content": "  World  "},
            {"role": "assistant", "content": "Hi there"},
        ],
        memory_hits=[], artifact_refs=[], tool_results=[],
        token_count=30, budget=500,
    )
    compactor = Compactor()
    result = compactor.process(session, ctx, budget=500)
    # Two consecutive user messages merged, whitespace trimmed
    assert len(result.history) == 2
    assert result.history[0]["role"] == "user"
    assert "Hello" in result.history[0]["content"]
    assert "World" in result.history[0]["content"]


def test_memory_preloader():
    mem = InMemoryBackend()
    mem.store("fact1", "Python is a programming language", "core")
    mem.store("fact2", "Rust is systems programming", "core")

    session = Session()
    session.record("user_input", {"text": "Tell me about Python"}, token_estimate=10)

    ctx = WorkingContext(
        system_prompt="test", history=[], memory_hits=[], artifact_refs=[],
        tool_results=[], token_count=10, budget=500,
    )
    preloader = MemoryPreloader(memory_service=mem, top_k=5)
    result = preloader.process(session, ctx, budget=500)
    assert len(result.memory_hits) >= 1


def test_artifact_attacher_externalizes_large():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SqliteArtifactStore(db_path=Path(tmpdir) / "art.db")
        try:
            # Build a large result with multiple words so estimate_tokens is meaningful
            big_text = " ".join(["word"] * 2000)  # ~2000 words -> ~2600 tokens
            session = Session()
            from ygn_brain.context_compiler.token_budget import estimate_tokens
            big_tokens = estimate_tokens(big_text)
            ctx = WorkingContext(
                system_prompt="test",
                history=[],
                memory_hits=[],
                artifact_refs=[],
                tool_results=[
                    {"tool": "big_tool", "result": big_text},
                ],
                token_count=big_tokens,
                budget=500,
            )
            attacher = ArtifactAttacher(artifact_store=store, threshold_bytes=1024)
            result = attacher.process(session, ctx, budget=500)

            # Large result externalized: tool_results cleared, artifact_ref added
            assert len(result.artifact_refs) == 1
            assert result.artifact_refs[0]["handle"]
            assert result.artifact_refs[0]["size_bytes"] >= len(big_text.encode("utf-8"))
            # Token count reduced (summary is much shorter than the original)
            assert result.token_count < big_tokens
        finally:
            store.close()  # Windows: release SQLite lock before tmpdir cleanup

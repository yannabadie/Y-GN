"""Tests for WorkingContext."""

from ygn_brain.context_compiler.working_context import WorkingContext


def test_budget_checking():
    ctx = WorkingContext(
        system_prompt="You are a helpful assistant.",
        history=[{"role": "user", "content": "hello"}],
        memory_hits=[],
        artifact_refs=[],
        tool_results=[],
        token_count=50,
        budget=100,
    )
    assert ctx.is_within_budget()
    assert ctx.overflow() == 0

    over = WorkingContext(
        system_prompt="x",
        history=[],
        memory_hits=[],
        artifact_refs=[],
        tool_results=[],
        token_count=150,
        budget=100,
    )
    assert not over.is_within_budget()
    assert over.overflow() == 50


def test_to_messages():
    ctx = WorkingContext(
        system_prompt="You are helpful.",
        history=[
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
        ],
        memory_hits=[{"key": "math", "content": "basic arithmetic"}],
        artifact_refs=[{"handle": "abc123", "summary": "large file", "size_bytes": 5000}],
        tool_results=[{"tool": "calc", "result": "4"}],
        token_count=80,
        budget=200,
    )
    msgs = ctx.to_messages()
    assert msgs[0]["role"] == "system"
    assert "You are helpful." in msgs[0]["content"]
    # Memory hits included in system context
    assert "basic arithmetic" in msgs[0]["content"]
    # Artifact refs mentioned
    assert "abc123" in msgs[0]["content"]
    # History messages follow
    assert msgs[1]["role"] == "user"
    assert msgs[2]["role"] == "assistant"

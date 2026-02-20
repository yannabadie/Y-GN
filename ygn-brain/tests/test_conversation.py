"""Tests for conversation memory module."""

from __future__ import annotations

from ygn_brain.conversation import ConversationMemory, ConversationTurn
from ygn_brain.provider import ChatRole


def test_add_and_retrieve_user_messages():
    mem = ConversationMemory()
    mem.add_user_message("Hello")
    mem.add_user_message("How are you?")
    assert len(mem.turns) == 2
    assert mem.turns[0].role == ChatRole.USER
    assert mem.turns[0].content == "Hello"
    assert mem.turns[1].content == "How are you?"


def test_add_and_retrieve_assistant_messages():
    mem = ConversationMemory()
    mem.add_assistant_message("I'm fine, thanks!")
    assert len(mem.turns) == 1
    assert mem.turns[0].role == ChatRole.ASSISTANT
    assert mem.turns[0].content == "I'm fine, thanks!"


def test_add_tool_result_with_metadata():
    mem = ConversationMemory()
    mem.add_tool_result("42", tool_name="calculator")
    assert len(mem.turns) == 1
    assert mem.turns[0].role == ChatRole.TOOL
    assert mem.turns[0].content == "42"
    assert mem.turns[0].metadata["tool_name"] == "calculator"


def test_to_messages_includes_system_prompt():
    mem = ConversationMemory()
    mem.set_system_prompt("You are helpful.")
    mem.add_user_message("Hi")
    messages = mem.to_messages()
    assert len(messages) == 2
    assert messages[0].role == ChatRole.SYSTEM
    assert messages[0].content == "You are helpful."
    assert messages[1].role == ChatRole.USER
    assert messages[1].content == "Hi"


def test_to_messages_without_system_prompt():
    mem = ConversationMemory()
    mem.add_user_message("Hi")
    mem.add_assistant_message("Hello!")
    messages = mem.to_messages()
    assert len(messages) == 2
    assert messages[0].role == ChatRole.USER
    assert messages[1].role == ChatRole.ASSISTANT


def test_trim_by_max_turns():
    mem = ConversationMemory(max_turns=3, max_tokens=100_000)
    for i in range(5):
        mem.add_user_message(f"msg {i}")
    assert len(mem.turns) == 3
    # Oldest messages should have been trimmed
    assert mem.turns[0].content == "msg 2"
    assert mem.turns[2].content == "msg 4"


def test_trim_by_max_tokens():
    # Each message is ~25 chars = ~6 tokens; max_tokens=10 means
    # only ~2 messages should fit.
    mem = ConversationMemory(max_turns=100, max_tokens=10)
    mem.add_user_message("a" * 20)  # 5 tokens
    mem.add_user_message("b" * 20)  # 5 tokens
    mem.add_user_message("c" * 20)  # 5 tokens
    # Should trim until estimated tokens <= 10, keeping at least 1
    assert len(mem.turns) <= 2


def test_clear_empties_all_turns():
    mem = ConversationMemory()
    mem.add_user_message("one")
    mem.add_assistant_message("two")
    mem.add_tool_result("three", tool_name="t")
    assert len(mem.turns) == 3
    mem.clear()
    assert len(mem.turns) == 0


def test_summary_returns_correct_stats():
    mem = ConversationMemory(max_turns=50, max_tokens=8000)
    mem.set_system_prompt("System prompt here")
    mem.add_user_message("Hello")
    mem.add_assistant_message("Hi there")
    s = mem.summary()
    assert s["turn_count"] == 2
    assert s["max_turns"] == 50
    assert s["max_tokens"] == 8000
    assert s["has_system_prompt"] is True
    assert isinstance(s["estimated_tokens"], int)
    assert s["estimated_tokens"] > 0


def test_turn_serialization():
    turn = ConversationTurn(
        role=ChatRole.USER,
        content="test content",
        timestamp=1000.0,
        metadata={"key": "value"},
    )
    data = turn.model_dump()
    assert data["role"] == "user"
    assert data["content"] == "test content"
    assert data["timestamp"] == 1000.0
    assert data["metadata"] == {"key": "value"}
    # Round-trip
    restored = ConversationTurn.model_validate(data)
    assert restored == turn


def test_user_message_metadata():
    mem = ConversationMemory()
    mem.add_user_message("Hi", source="web", priority=1)
    assert mem.turns[0].metadata["source"] == "web"
    assert mem.turns[0].metadata["priority"] == 1


def test_system_prompt_property():
    mem = ConversationMemory()
    assert mem.system_prompt is None
    mem.set_system_prompt("Be helpful")
    assert mem.system_prompt == "Be helpful"

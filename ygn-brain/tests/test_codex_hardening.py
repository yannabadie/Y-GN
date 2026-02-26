"""Tests for Codex CLI provider hardening — is_available + JSONL edge cases."""

from __future__ import annotations

from unittest.mock import patch

from ygn_brain.codex_provider import CodexCliProvider
from ygn_brain.provider import TokenUsage

# ---------------------------------------------------------------------------
# is_available()
# ---------------------------------------------------------------------------


def test_codex_is_available_returns_bool() -> None:
    """is_available() should return a bool without crashing."""
    provider = CodexCliProvider()
    result = provider.is_available()
    assert isinstance(result, bool)


@patch("shutil.which", return_value="/usr/bin/codex")
def test_codex_is_available_true_when_codex_found(mock_which) -> None:  # noqa: ANN001
    """is_available() returns True when `codex` is on PATH."""
    provider = CodexCliProvider()
    assert provider.is_available() is True


@patch("shutil.which", return_value=None)
def test_codex_is_available_false_when_codex_missing(mock_which) -> None:  # noqa: ANN001
    """is_available() returns False when neither codex nor codex.cmd is on PATH."""
    provider = CodexCliProvider()
    assert provider.is_available() is False


@patch("shutil.which", side_effect=lambda name: "C:\\codex.cmd" if name == "codex.cmd" else None)
def test_codex_is_available_finds_codex_cmd(mock_which) -> None:  # noqa: ANN001
    """is_available() returns True when codex.cmd is found (Windows npm install)."""
    provider = CodexCliProvider()
    assert provider.is_available() is True


# ---------------------------------------------------------------------------
# _parse_jsonl_response — edge cases
# ---------------------------------------------------------------------------


def test_codex_parse_empty_response() -> None:
    """Empty string should not crash; returns empty content + zero usage."""
    content, usage = CodexCliProvider._parse_jsonl_response("")
    assert isinstance(content, str)
    assert isinstance(usage, TokenUsage)
    # Empty input => fallback is the empty string itself
    assert content == ""
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0


def test_codex_parse_whitespace_only() -> None:
    """Whitespace-only input should behave like empty."""
    content, usage = CodexCliProvider._parse_jsonl_response("   \n\n  \n  ")
    assert isinstance(content, str)
    assert isinstance(usage, TokenUsage)
    assert usage.prompt_tokens == 0


def test_codex_parse_partial_jsonl() -> None:
    """Truncated/partial JSON line should be skipped gracefully."""
    partial = '{"type": "item.completed", "item": {"type": "agent_message"'
    content, usage = CodexCliProvider._parse_jsonl_response(partial)
    assert isinstance(content, str)
    assert isinstance(usage, TokenUsage)
    # The malformed line is skipped; fallback to raw stdout
    assert content == partial


def test_codex_parse_mixed_valid_and_invalid() -> None:
    """Valid lines are extracted; invalid lines are silently skipped."""
    lines = (
        '{"type":"item.completed","item":{"type":"agent_message","text":"Good"}}\n'
        "NOT-JSON-AT-ALL\n"
        '{"type":"turn.completed","usage":{"input_tokens":7,"output_tokens":3}}'
    )
    content, usage = CodexCliProvider._parse_jsonl_response(lines)
    assert content == "Good"
    assert usage.prompt_tokens == 7
    assert usage.completion_tokens == 3


def test_codex_parse_multiple_agent_messages() -> None:
    """Multiple agent_message items are joined with newlines."""
    lines = (
        '{"type":"item.completed","item":{"type":"agent_message","text":"Line 1"}}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"Line 2"}}'
    )
    content, usage = CodexCliProvider._parse_jsonl_response(lines)
    assert content == "Line 1\nLine 2"
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0

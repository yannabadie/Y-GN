"""Tests for the REPL module — interactive CLI entry points."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ygn_brain.repl import _print_result, async_main, main

# ---------------------------------------------------------------------------
# main() — synchronous REPL
# ---------------------------------------------------------------------------


def test_main_quit_command(capsys: pytest.CaptureFixture[str]) -> None:
    """main() should exit cleanly on 'quit'."""
    with patch("builtins.input", side_effect=["quit"]):
        main()
    captured = capsys.readouterr()
    assert "Y-GN Brain REPL v0.1.0" in captured.out
    assert "Bye!" in captured.out


def test_main_exit_command(capsys: pytest.CaptureFixture[str]) -> None:
    """main() should exit cleanly on 'exit'."""
    with patch("builtins.input", side_effect=["exit"]):
        main()
    captured = capsys.readouterr()
    assert "Bye!" in captured.out


def test_main_eof(capsys: pytest.CaptureFixture[str]) -> None:
    """main() should handle EOFError gracefully."""
    with patch("builtins.input", side_effect=EOFError):
        main()
    captured = capsys.readouterr()
    assert "Bye!" in captured.out


def test_main_keyboard_interrupt(capsys: pytest.CaptureFixture[str]) -> None:
    """main() should handle KeyboardInterrupt gracefully."""
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        main()
    captured = capsys.readouterr()
    assert "Bye!" in captured.out


def test_main_processes_task(capsys: pytest.CaptureFixture[str]) -> None:
    """main() should process a task through the orchestrator pipeline."""
    with patch("builtins.input", side_effect=["hello world", "quit"]):
        main()
    captured = capsys.readouterr()
    # Should print a session_id and result
    assert "[" in captured.out  # session_id in brackets
    assert "hello world" in captured.out


def test_main_status_command(capsys: pytest.CaptureFixture[str]) -> None:
    """main() should print pipeline status on 'status' command."""
    with patch("builtins.input", side_effect=["status", "quit"]):
        main()
    captured = capsys.readouterr()
    assert "FSM state:" in captured.out
    assert "Session:" in captured.out
    assert "Evidence entries:" in captured.out


def test_main_help_command(capsys: pytest.CaptureFixture[str]) -> None:
    """main() should print help on 'help' command."""
    with patch("builtins.input", side_effect=["help", "quit"]):
        main()
    captured = capsys.readouterr()
    assert "Commands:" in captured.out
    assert "status" in captured.out
    assert "quit" in captured.out


def test_main_empty_input_is_skipped(capsys: pytest.CaptureFixture[str]) -> None:
    """main() should ignore empty lines."""
    with patch("builtins.input", side_effect=["", "  ", "quit"]):
        main()
    captured = capsys.readouterr()
    assert "Bye!" in captured.out


# ---------------------------------------------------------------------------
# async_main() — async REPL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_main_quit(capsys: pytest.CaptureFixture[str]) -> None:
    """async_main() should exit on 'quit'."""
    with patch("builtins.input", side_effect=["quit"]):
        await async_main()
    captured = capsys.readouterr()
    assert "REPL v0.1.0 (async)" in captured.out
    assert "Bye!" in captured.out


@pytest.mark.asyncio
async def test_async_main_processes_task(capsys: pytest.CaptureFixture[str]) -> None:
    """async_main() should process a task through the async pipeline."""
    with patch("builtins.input", side_effect=["hello world", "quit"]):
        await async_main()
    captured = capsys.readouterr()
    assert "[" in captured.out
    assert "stub response" in captured.out


@pytest.mark.asyncio
async def test_async_main_status(capsys: pytest.CaptureFixture[str]) -> None:
    """async_main() should print status info."""
    with patch("builtins.input", side_effect=["status", "quit"]):
        await async_main()
    captured = capsys.readouterr()
    assert "FSM state:" in captured.out
    assert "Session:" in captured.out


@pytest.mark.asyncio
async def test_async_main_eof(capsys: pytest.CaptureFixture[str]) -> None:
    """async_main() should handle EOF gracefully."""
    with patch("builtins.input", side_effect=EOFError):
        await async_main()
    captured = capsys.readouterr()
    assert "Bye!" in captured.out


# ---------------------------------------------------------------------------
# _print_result helper
# ---------------------------------------------------------------------------


def test_print_result_normal(capsys: pytest.CaptureFixture[str]) -> None:
    """_print_result should display session_id and result."""
    _print_result({"session_id": "abc123", "result": "answer"})
    captured = capsys.readouterr()
    assert "[abc123]" in captured.out
    assert "answer" in captured.out


def test_print_result_blocked(capsys: pytest.CaptureFixture[str]) -> None:
    """_print_result should warn when input was blocked."""
    _print_result({"session_id": "x", "result": "Blocked", "blocked": True})
    captured = capsys.readouterr()
    assert "Warning" in captured.out
    assert "blocked" in captured.out.lower()

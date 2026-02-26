"""Tests for GeminiCliProvider — mocked subprocess, no real gemini CLI required."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ygn_brain.gemini_provider import GeminiCliError, GeminiCliProvider
from ygn_brain.provider import ChatMessage, ChatRequest, ChatRole, LLMProvider, ToolSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(content: str = "hello", model: str = "gemini-3.1-pro-preview") -> ChatRequest:
    return ChatRequest(
        model=model,
        messages=[ChatMessage(role=ChatRole.USER, content=content)],
    )


def _mock_process(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode

    async def communicate() -> tuple[bytes, bytes]:
        return stdout.encode(), stderr.encode()

    proc.communicate = communicate  # type: ignore[assignment]
    return proc


# ---------------------------------------------------------------------------
# Basic identity
# ---------------------------------------------------------------------------


def test_gemini_provider_name() -> None:
    p = GeminiCliProvider()
    assert p.name() == "gemini"


def test_gemini_provider_is_llm_provider() -> None:
    p = GeminiCliProvider()
    assert isinstance(p, LLMProvider)


def test_gemini_provider_capabilities() -> None:
    p = GeminiCliProvider()
    caps = p.capabilities()
    assert caps.native_tool_calling is False
    assert caps.vision is False
    assert caps.streaming is False


def test_gemini_provider_default_model() -> None:
    p = GeminiCliProvider()
    assert p.model == "gemini-3.1-pro-preview"


def test_gemini_provider_custom_model() -> None:
    p = GeminiCliProvider(model="custom-gemini")
    assert p.model == "custom-gemini"


def test_gemini_provider_env_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YGN_GEMINI_MODEL", "gemini-2.0-flash")
    p = GeminiCliProvider()
    assert p.model == "gemini-2.0-flash"


def test_gemini_provider_env_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YGN_LLM_TIMEOUT_SEC", "120")
    p = GeminiCliProvider()
    assert p._timeout == 120.0  # noqa: SLF001


# ---------------------------------------------------------------------------
# chat() — success with JSON response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/gemini")
@patch("asyncio.create_subprocess_exec")
async def test_gemini_chat_json_response(mock_exec: AsyncMock, mock_which: MagicMock) -> None:
    """Gemini returns JSON with .response field."""
    json_out = json.dumps({"response": "The answer is 42"})
    proc = _mock_process(stdout=json_out)
    mock_exec.return_value = proc

    p = GeminiCliProvider()
    resp = await p.chat(_make_request())

    assert resp.content == "The answer is 42"
    assert resp.tool_calls == []
    assert resp.usage is not None


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/gemini")
@patch("asyncio.create_subprocess_exec")
async def test_gemini_chat_json_text_field(mock_exec: AsyncMock, mock_which: MagicMock) -> None:
    """Gemini returns JSON with .text field."""
    json_out = json.dumps({"text": "Alternative field"})
    proc = _mock_process(stdout=json_out)
    mock_exec.return_value = proc

    p = GeminiCliProvider()
    resp = await p.chat(_make_request())
    assert resp.content == "Alternative field"


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/gemini")
@patch("asyncio.create_subprocess_exec")
async def test_gemini_chat_raw_text_fallback(mock_exec: AsyncMock, mock_which: MagicMock) -> None:
    """Gemini returns plain text (not JSON)."""
    proc = _mock_process(stdout="Just plain text response")
    mock_exec.return_value = proc

    p = GeminiCliProvider()
    resp = await p.chat(_make_request())
    assert resp.content == "Just plain text response"


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/gemini")
@patch("asyncio.create_subprocess_exec")
async def test_gemini_chat_passes_model(mock_exec: AsyncMock, mock_which: MagicMock) -> None:
    proc = _mock_process(stdout='{"response": "ok"}')
    mock_exec.return_value = proc

    p = GeminiCliProvider()
    await p.chat(_make_request(model="gemini-3.1-pro-preview"))

    call_args = mock_exec.call_args[0]
    assert "gemini-3.1-pro-preview" in call_args


# ---------------------------------------------------------------------------
# chat() — errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("shutil.which", return_value=None)
async def test_gemini_chat_binary_not_found(mock_which: MagicMock) -> None:
    p = GeminiCliProvider()
    with pytest.raises(GeminiCliError, match="gemini CLI not found"):
        await p.chat(_make_request())


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/gemini")
@patch("asyncio.create_subprocess_exec")
async def test_gemini_chat_nonzero_exit(mock_exec: AsyncMock, mock_which: MagicMock) -> None:
    proc = _mock_process(stderr="quota exceeded", returncode=1)
    mock_exec.return_value = proc

    p = GeminiCliProvider()
    with pytest.raises(GeminiCliError, match="exit 1.*quota"):
        await p.chat(_make_request())


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/gemini")
@patch("asyncio.create_subprocess_exec")
async def test_gemini_chat_auth_error(mock_exec: AsyncMock, mock_which: MagicMock) -> None:
    proc = _mock_process(stderr="Authentication failed: login required", returncode=1)
    mock_exec.return_value = proc

    p = GeminiCliProvider()
    with pytest.raises(GeminiCliError, match="auth error.*login"):
        await p.chat(_make_request())


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/gemini")
@patch("asyncio.create_subprocess_exec")
async def test_gemini_chat_timeout(mock_exec: AsyncMock, mock_which: MagicMock) -> None:
    proc = MagicMock()

    async def slow_communicate() -> tuple[bytes, bytes]:
        await asyncio.sleep(999)
        return b"", b""  # pragma: no cover

    proc.communicate = slow_communicate  # type: ignore[assignment]
    mock_exec.return_value = proc

    p = GeminiCliProvider(timeout=0.01)
    with pytest.raises(GeminiCliError, match="timed out"):
        await p.chat(_make_request())


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------


def test_parse_response_json_response_field() -> None:
    raw = json.dumps({"response": "hello world"})
    assert GeminiCliProvider._parse_response(raw) == "hello world"


def test_parse_response_json_content_field() -> None:
    raw = json.dumps({"content": "content value"})
    assert GeminiCliProvider._parse_response(raw) == "content value"


def test_parse_response_json_output_field() -> None:
    raw = json.dumps({"output": "output value"})
    assert GeminiCliProvider._parse_response(raw) == "output value"


def test_parse_response_json_unknown_keys() -> None:
    raw = json.dumps({"foo": "bar"})
    result = GeminiCliProvider._parse_response(raw)
    assert "foo" in result  # stringified JSON


def test_parse_response_plain_text() -> None:
    assert GeminiCliProvider._parse_response("plain text") == "plain text"


def test_parse_response_empty() -> None:
    assert GeminiCliProvider._parse_response("") == ""


# ---------------------------------------------------------------------------
# chat_with_tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/gemini")
@patch("asyncio.create_subprocess_exec")
async def test_gemini_chat_with_tools_injects_text(
    mock_exec: AsyncMock, mock_which: MagicMock
) -> None:
    proc = _mock_process(stdout='{"response": "use calculator"}')
    mock_exec.return_value = proc

    p = GeminiCliProvider()
    tools = [ToolSpec(name="calculator", description="Does math")]
    resp = await p.chat_with_tools(_make_request("2+2"), tools)

    assert resp.content == "use calculator"
    call_args = mock_exec.call_args[0]
    prompt_arg = call_args[2]  # --prompt value
    assert "calculator" in prompt_arg

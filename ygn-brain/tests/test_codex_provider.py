"""Tests for CodexCliProvider — mocked subprocess, no real codex required."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ygn_brain.codex_provider import CodexCliError, CodexCliProvider
from ygn_brain.provider import ChatMessage, ChatRequest, ChatRole, LLMProvider, ToolSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(content: str = "hello", model: str = "gpt-5.3-codex") -> ChatRequest:
    return ChatRequest(
        model=model,
        messages=[ChatMessage(role=ChatRole.USER, content=content)],
    )


def _mock_process(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    """Create a mock asyncio.subprocess.Process."""
    proc = MagicMock()
    proc.returncode = returncode

    async def communicate() -> tuple[bytes, bytes]:
        return stdout.encode(), stderr.encode()

    proc.communicate = communicate  # type: ignore[assignment]
    return proc


# ---------------------------------------------------------------------------
# Basic identity
# ---------------------------------------------------------------------------


def test_codex_provider_name() -> None:
    p = CodexCliProvider()
    assert p.name() == "codex"


def test_codex_provider_is_llm_provider() -> None:
    p = CodexCliProvider()
    assert isinstance(p, LLMProvider)


def test_codex_provider_capabilities() -> None:
    p = CodexCliProvider()
    caps = p.capabilities()
    assert caps.native_tool_calling is False
    assert caps.vision is False
    assert caps.streaming is False


def test_codex_provider_default_model() -> None:
    p = CodexCliProvider()
    assert p.model == "gpt-5.3-codex"


def test_codex_provider_custom_model() -> None:
    p = CodexCliProvider(model="custom-model")
    assert p.model == "custom-model"


def test_codex_provider_env_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YGN_CODEX_MODEL", "env-model")
    p = CodexCliProvider()
    assert p.model == "env-model"


def test_codex_provider_env_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YGN_LLM_TIMEOUT_SEC", "60")
    p = CodexCliProvider()
    assert p._timeout == 60.0  # noqa: SLF001


# ---------------------------------------------------------------------------
# chat() — success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/codex")
@patch("asyncio.create_subprocess_exec")
async def test_codex_chat_success(
    mock_exec: AsyncMock, mock_which: MagicMock
) -> None:
    proc = _mock_process(stdout="This is the LLM response")
    mock_exec.return_value = proc

    p = CodexCliProvider()
    resp = await p.chat(_make_request("test prompt"))

    assert resp.content == "This is the LLM response"
    assert resp.tool_calls == []
    assert resp.usage is not None
    assert resp.usage.prompt_tokens > 0
    assert resp.usage.completion_tokens > 0
    mock_exec.assert_called_once()


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/codex")
@patch("asyncio.create_subprocess_exec")
async def test_codex_chat_passes_model(
    mock_exec: AsyncMock, mock_which: MagicMock
) -> None:
    proc = _mock_process(stdout="ok")
    mock_exec.return_value = proc

    p = CodexCliProvider()
    await p.chat(_make_request("hi", model="gpt-5.3-codex"))

    # Verify model is passed as arg
    call_args = mock_exec.call_args[0]
    assert "gpt-5.3-codex" in call_args


# ---------------------------------------------------------------------------
# chat() — errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("shutil.which", return_value=None)
async def test_codex_chat_binary_not_found(mock_which: MagicMock) -> None:
    p = CodexCliProvider()
    with pytest.raises(CodexCliError, match="codex CLI not found"):
        await p.chat(_make_request())


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/codex")
@patch("asyncio.create_subprocess_exec")
async def test_codex_chat_nonzero_exit(
    mock_exec: AsyncMock, mock_which: MagicMock
) -> None:
    proc = _mock_process(stderr="rate limit exceeded", returncode=1)
    mock_exec.return_value = proc

    p = CodexCliProvider()
    with pytest.raises(CodexCliError, match="exit 1.*rate limit"):
        await p.chat(_make_request())


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/codex")
@patch("asyncio.create_subprocess_exec")
async def test_codex_chat_timeout(
    mock_exec: AsyncMock, mock_which: MagicMock
) -> None:
    proc = MagicMock()

    async def slow_communicate() -> tuple[bytes, bytes]:
        await asyncio.sleep(999)
        return b"", b""  # pragma: no cover

    proc.communicate = slow_communicate  # type: ignore[assignment]
    mock_exec.return_value = proc

    p = CodexCliProvider(timeout=0.01)
    with pytest.raises(CodexCliError, match="timed out"):
        await p.chat(_make_request())


# ---------------------------------------------------------------------------
# chat_with_tools() — MVP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/codex")
@patch("asyncio.create_subprocess_exec")
async def test_codex_chat_with_tools_injects_tool_text(
    mock_exec: AsyncMock, mock_which: MagicMock
) -> None:
    proc = _mock_process(stdout="I would use search")
    mock_exec.return_value = proc

    p = CodexCliProvider()
    tools = [ToolSpec(name="search", description="Search the web")]
    resp = await p.chat_with_tools(_make_request("find something"), tools)

    assert resp.content == "I would use search"
    # Verify the tool description was included in the prompt
    call_args = mock_exec.call_args[0]
    prompt_arg = call_args[2]  # 3rd arg to exec is the prompt
    assert "search" in prompt_arg


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/codex")
@patch("asyncio.create_subprocess_exec")
async def test_codex_chat_with_tools_empty_list(
    mock_exec: AsyncMock, mock_which: MagicMock
) -> None:
    proc = _mock_process(stdout="plain response")
    mock_exec.return_value = proc

    p = CodexCliProvider()
    resp = await p.chat_with_tools(_make_request(), [])
    assert resp.content == "plain response"


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


def test_build_prompt_combines_messages() -> None:
    req = ChatRequest(
        model="m",
        messages=[
            ChatMessage(role=ChatRole.SYSTEM, content="You are helpful."),
            ChatMessage(role=ChatRole.USER, content="Hello"),
        ],
    )
    prompt = CodexCliProvider._build_prompt(req)
    assert "[System] You are helpful." in prompt
    assert "Hello" in prompt

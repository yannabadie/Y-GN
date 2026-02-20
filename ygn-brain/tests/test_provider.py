"""Tests for provider module — LLMProvider ABC, types, and StubLLMProvider."""

from __future__ import annotations

import pytest

from ygn_brain.provider import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    LLMProvider,
    ProviderCapabilities,
    StubLLMProvider,
    TokenUsage,
    ToolCall,
    ToolSpec,
)

# ---------------------------------------------------------------------------
# ChatRole enum
# ---------------------------------------------------------------------------


def test_chat_role_values():
    assert ChatRole.SYSTEM == "system"
    assert ChatRole.USER == "user"
    assert ChatRole.ASSISTANT == "assistant"
    assert ChatRole.TOOL == "tool"


def test_chat_role_is_str():
    # StrEnum members are also strings
    assert isinstance(ChatRole.USER, str)


# ---------------------------------------------------------------------------
# Pydantic model serialization
# ---------------------------------------------------------------------------


def test_chat_message_serialization():
    msg = ChatMessage(role=ChatRole.USER, content="hello")
    data = msg.model_dump()
    assert data["role"] == "user"
    assert data["content"] == "hello"


def test_chat_request_serialization():
    req = ChatRequest(
        model="test-model",
        messages=[ChatMessage(role=ChatRole.USER, content="hi")],
        max_tokens=100,
        temperature=0.7,
    )
    data = req.model_dump()
    assert data["model"] == "test-model"
    assert len(data["messages"]) == 1
    assert data["max_tokens"] == 100
    assert data["temperature"] == 0.7


def test_chat_request_optional_fields_default_none():
    req = ChatRequest(
        model="m",
        messages=[],
    )
    assert req.max_tokens is None
    assert req.temperature is None


def test_chat_response_serialization():
    resp = ChatResponse(
        content="answer",
        tool_calls=[ToolCall(tool_name="search", arguments={"q": "test"})],
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
    )
    data = resp.model_dump()
    assert data["content"] == "answer"
    assert len(data["tool_calls"]) == 1
    assert data["tool_calls"][0]["tool_name"] == "search"
    assert data["usage"]["prompt_tokens"] == 10


def test_chat_response_defaults():
    resp = ChatResponse(content="ok")
    assert resp.tool_calls == []
    assert resp.usage is None


def test_tool_spec_serialization():
    spec = ToolSpec(
        name="calculator",
        description="Does math",
        parameters={"expression": {"type": "string"}},
    )
    data = spec.model_dump()
    assert data["name"] == "calculator"
    assert "expression" in data["parameters"]


# ---------------------------------------------------------------------------
# StubLLMProvider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stub_provider_name():
    provider = StubLLMProvider()
    assert provider.name() == "stub"


@pytest.mark.asyncio
async def test_stub_provider_capabilities():
    provider = StubLLMProvider()
    caps = provider.capabilities()
    assert isinstance(caps, ProviderCapabilities)
    assert caps.native_tool_calling is False
    assert caps.vision is False
    assert caps.streaming is False


@pytest.mark.asyncio
async def test_stub_provider_chat_returns_canned_response():
    provider = StubLLMProvider()
    req = ChatRequest(
        model="test-model",
        messages=[ChatMessage(role=ChatRole.USER, content="hello world")],
    )
    resp = await provider.chat(req)
    assert "stub response" in resp.content
    assert "test-model" in resp.content
    assert resp.tool_calls == []
    assert resp.usage is not None
    assert resp.usage.prompt_tokens > 0
    assert resp.usage.completion_tokens > 0


@pytest.mark.asyncio
async def test_stub_provider_chat_with_tools():
    provider = StubLLMProvider()
    req = ChatRequest(
        model="m",
        messages=[ChatMessage(role=ChatRole.USER, content="find x")],
    )
    tools = [ToolSpec(name="search", description="Search the web")]
    resp = await provider.chat_with_tools(req, tools)
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].tool_name == "search"


@pytest.mark.asyncio
async def test_stub_provider_chat_with_tools_no_tools():
    provider = StubLLMProvider()
    req = ChatRequest(
        model="m",
        messages=[ChatMessage(role=ChatRole.USER, content="hi")],
    )
    resp = await provider.chat_with_tools(req, [])
    assert resp.tool_calls == []


def test_stub_provider_is_llm_provider():
    provider = StubLLMProvider()
    assert isinstance(provider, LLMProvider)

"""LLM Provider abstraction — pluggable backend for real and stub LLMs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class ProviderCapabilities(BaseModel):
    """Declares what a provider can do."""

    native_tool_calling: bool = False
    vision: bool = False
    streaming: bool = False


class ChatRole(StrEnum):
    """Role of a message participant."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """Single message in a conversation."""

    role: ChatRole
    content: str


class ChatRequest(BaseModel):
    """Request payload sent to an LLM provider."""

    model: str
    messages: list[ChatMessage]
    max_tokens: int | None = None
    temperature: float | None = None


class ToolSpec(BaseModel):
    """Specification for a tool that an LLM can call."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A tool invocation returned by the LLM."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    """Token consumption metrics for a single request."""

    prompt_tokens: int
    completion_tokens: int


class ChatResponse(BaseModel):
    """Response returned from an LLM provider."""

    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage | None = None


# ---------------------------------------------------------------------------
# LLMProvider ABC
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def name(self) -> str:
        """Return the canonical provider name (e.g. 'claude', 'openai')."""

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Describe what this provider supports."""

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat completion request."""

    @abstractmethod
    async def chat_with_tools(self, request: ChatRequest, tools: list[ToolSpec]) -> ChatResponse:
        """Send a chat completion request with tool definitions."""


# ---------------------------------------------------------------------------
# Stub implementation (for testing / offline development)
# ---------------------------------------------------------------------------


class StubLLMProvider(LLMProvider):
    """Returns canned responses without making real HTTP calls."""

    _CANNED = "This is a stub response for testing purposes."

    def name(self) -> str:
        return "stub"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_tool_calling=False,
            vision=False,
            streaming=False,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Return a deterministic canned response."""
        prompt_tokens = sum(len(m.content.split()) for m in request.messages)
        reply = f"{self._CANNED} (model={request.model})"
        return ChatResponse(
            content=reply,
            tool_calls=[],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=len(reply.split()),
            ),
        )

    async def chat_with_tools(self, request: ChatRequest, tools: list[ToolSpec]) -> ChatResponse:
        """Return a canned response that includes a stub tool call when tools are provided."""
        base = await self.chat(request)
        if tools:
            base.tool_calls = [
                ToolCall(
                    tool_name=tools[0].name,
                    arguments={"input": "stub"},
                )
            ]
        return base

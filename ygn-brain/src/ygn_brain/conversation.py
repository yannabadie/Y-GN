"""Multi-turn conversation memory with context window management."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from .provider import ChatMessage, ChatRole


class ConversationTurn(BaseModel):
    """A single turn in a conversation."""

    role: ChatRole
    content: str
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationMemory:
    """Manages multi-turn conversation history with context window limits."""

    def __init__(
        self,
        max_turns: int = 50,
        max_tokens: int = 8000,
    ) -> None:
        self._turns: list[ConversationTurn] = []
        self._max_turns = max_turns
        self._max_tokens = max_tokens
        self._system_prompt: str | None = None

    @property
    def turns(self) -> list[ConversationTurn]:
        return list(self._turns)

    @property
    def system_prompt(self) -> str | None:
        return self._system_prompt

    def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt

    def add_user_message(self, content: str, **metadata: Any) -> None:
        self._turns.append(
            ConversationTurn(
                role=ChatRole.USER,
                content=content,
                metadata=metadata,
            )
        )
        self._trim()

    def add_assistant_message(self, content: str, **metadata: Any) -> None:
        self._turns.append(
            ConversationTurn(
                role=ChatRole.ASSISTANT,
                content=content,
                metadata=metadata,
            )
        )
        self._trim()

    def add_tool_result(self, content: str, tool_name: str) -> None:
        self._turns.append(
            ConversationTurn(
                role=ChatRole.TOOL,
                content=content,
                metadata={"tool_name": tool_name},
            )
        )
        self._trim()

    def to_messages(self) -> list[ChatMessage]:
        """Convert conversation to ChatMessage list for LLM calls."""
        messages: list[ChatMessage] = []
        if self._system_prompt:
            messages.append(ChatMessage(role=ChatRole.SYSTEM, content=self._system_prompt))
        for turn in self._turns:
            messages.append(ChatMessage(role=turn.role, content=turn.content))
        return messages

    def clear(self) -> None:
        self._turns.clear()

    def summary(self) -> dict[str, Any]:
        """Return a summary of the conversation state."""
        return {
            "turn_count": len(self._turns),
            "max_turns": self._max_turns,
            "max_tokens": self._max_tokens,
            "has_system_prompt": self._system_prompt is not None,
            "estimated_tokens": self._estimate_tokens(),
        }

    def _trim(self) -> None:
        """Trim oldest turns to stay within limits."""
        # Trim by turn count
        while len(self._turns) > self._max_turns:
            self._turns.pop(0)
        # Trim by estimated token count
        while self._estimate_tokens() > self._max_tokens and len(self._turns) > 1:
            self._turns.pop(0)

    def _estimate_tokens(self) -> int:
        """Rough token estimate (4 chars per token)."""
        total = sum(len(t.content) for t in self._turns)
        if self._system_prompt:
            total += len(self._system_prompt)
        return total // 4

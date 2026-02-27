"""WorkingContext — compiled view of a Session, ready for LLM consumption."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class WorkingContext:
    """Budget-aware compiled context for LLM calls."""

    system_prompt: str
    history: list[dict[str, Any]]
    memory_hits: list[dict[str, Any]]
    artifact_refs: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    token_count: int
    budget: int

    def is_within_budget(self) -> bool:
        return self.token_count <= self.budget

    def overflow(self) -> int:
        return max(0, self.token_count - self.budget)

    def to_messages(self) -> list[dict[str, str]]:
        """Format as message list for LLM provider.chat()."""
        parts = [self.system_prompt]

        if self.memory_hits:
            parts.append("\n\n## Relevant memories")
            for hit in self.memory_hits:
                parts.append(f"- [{hit.get('key', '')}]: {hit.get('content', '')}")

        if self.artifact_refs:
            parts.append("\n\n## Available artifacts (use handle to retrieve)")
            for ref in self.artifact_refs:
                handle = ref.get("handle", "")
                summary = ref.get("summary", "")
                size = ref.get("size_bytes", 0)
                parts.append(f"- [{handle}] ({size} bytes): {summary}")

        if self.tool_results:
            parts.append("\n\n## Recent tool results")
            for tr in self.tool_results:
                tool = tr.get("tool", "unknown")
                result = tr.get("result", "")
                parts.append(f"- {tool}: {result}")

        system_msg = {"role": "system", "content": "\n".join(parts)}
        messages: list[dict[str, str]] = [system_msg]
        messages.extend(
            {"role": h["role"], "content": h["content"]}
            for h in self.history
        )
        return messages

"""Token budget tracker — configurable, no hardcoded default."""

from __future__ import annotations

import math


def estimate_tokens(text: str) -> int:
    """Estimate token count from text. Rough heuristic: words * 1.3."""
    if not text:
        return 0
    words = len(text.split())
    return math.ceil(words * 1.3)


class TokenBudget:
    """Tracks token consumption against a configured maximum."""

    def __init__(self, max_tokens: int) -> None:
        if max_tokens <= 0:
            msg = "max_tokens must be positive"
            raise ValueError(msg)
        self._max = max_tokens
        self._consumed = 0

    def consume(self, tokens: int) -> None:
        self._consumed += tokens

    def remaining(self) -> int:
        return self._max - self._consumed

    def is_within_budget(self) -> bool:
        return self._consumed <= self._max

    def overflow(self) -> int:
        return max(0, self._consumed - self._max)

    @property
    def max_tokens(self) -> int:
        return self._max

    @property
    def consumed(self) -> int:
        return self._consumed

"""Context Compression — reduce context window usage via multiple strategies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CompressionStrategy(StrEnum):
    """Available compression strategies."""

    TRUNCATE = "truncate"
    SUMMARIZE = "summarize"
    SLIDING_WINDOW = "sliding_window"
    PRIORITY = "priority"


@dataclass
class CompressedContext:
    """Result of compressing a list of context items."""

    original_length: int
    compressed_length: int
    strategy_used: CompressionStrategy
    content: str
    dropped_count: int


class ContextCompressor:
    """Compresses context items to fit within a token budget."""

    def __init__(
        self,
        max_tokens: int = 4096,
        strategy: CompressionStrategy = CompressionStrategy.SLIDING_WINDOW,
    ) -> None:
        self._max_tokens = max_tokens
        self._strategy = strategy

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using a word-count / 0.75 approximation."""
        if not text:
            return 0
        words = text.split()
        return int(len(words) / 0.75)

    def fits(self, text: str) -> bool:
        """Check whether *text* fits within the max-token budget."""
        return self.estimate_tokens(text) <= self._max_tokens

    def compress(
        self,
        items: list[str],
        priorities: list[float] | None = None,
    ) -> CompressedContext:
        """Compress a list of context items using the configured strategy."""
        original_length = sum(self.estimate_tokens(item) for item in items)

        if not items:
            return CompressedContext(
                original_length=0,
                compressed_length=0,
                strategy_used=self._strategy,
                content="",
                dropped_count=0,
            )

        if self._strategy == CompressionStrategy.TRUNCATE:
            return self._truncate(items, original_length)
        if self._strategy == CompressionStrategy.SLIDING_WINDOW:
            return self._sliding_window(items, original_length)
        if self._strategy == CompressionStrategy.PRIORITY:
            return self._priority(items, priorities, original_length)
        # SUMMARIZE
        return self._summarize(items, original_length)

    # ------------------------------------------------------------------
    # Strategy implementations
    # ------------------------------------------------------------------

    def _truncate(self, items: list[str], original_length: int) -> CompressedContext:
        """Keep first N items that fit in max_tokens."""
        kept: list[str] = []
        budget = self._max_tokens
        for item in items:
            cost = self.estimate_tokens(item)
            if cost > budget:
                break
            kept.append(item)
            budget -= cost

        content = "\n".join(kept)
        return CompressedContext(
            original_length=original_length,
            compressed_length=self.estimate_tokens(content),
            strategy_used=CompressionStrategy.TRUNCATE,
            content=content,
            dropped_count=len(items) - len(kept),
        )

    def _sliding_window(self, items: list[str], original_length: int) -> CompressedContext:
        """Keep last N items (most recent) that fit in max_tokens."""
        kept: list[str] = []
        budget = self._max_tokens
        for item in reversed(items):
            cost = self.estimate_tokens(item)
            if cost > budget:
                break
            kept.append(item)
            budget -= cost

        kept.reverse()  # restore original order
        content = "\n".join(kept)
        return CompressedContext(
            original_length=original_length,
            compressed_length=self.estimate_tokens(content),
            strategy_used=CompressionStrategy.SLIDING_WINDOW,
            content=content,
            dropped_count=len(items) - len(kept),
        )

    def _priority(
        self,
        items: list[str],
        priorities: list[float] | None,
        original_length: int,
    ) -> CompressedContext:
        """Sort by priority scores descending, keep highest until full."""
        if priorities is None:
            priorities = [0.0] * len(items)

        indexed: list[tuple[float, int, str]] = [
            (priorities[i], i, items[i]) for i in range(len(items))
        ]
        indexed.sort(key=lambda t: t[0], reverse=True)

        kept_indices: list[int] = []
        budget = self._max_tokens
        for _priority, idx, item in indexed:
            cost = self.estimate_tokens(item)
            if cost > budget:
                continue  # skip this item, try smaller ones
            kept_indices.append(idx)
            budget -= cost

        # Restore original ordering for kept items
        kept_indices.sort()
        kept = [items[i] for i in kept_indices]

        content = "\n".join(kept)
        return CompressedContext(
            original_length=original_length,
            compressed_length=self.estimate_tokens(content),
            strategy_used=CompressionStrategy.PRIORITY,
            content=content,
            dropped_count=len(items) - len(kept),
        )

    def _summarize(self, items: list[str], original_length: int) -> CompressedContext:
        """Concatenate with separator, truncate if over limit."""
        separator = " | "
        combined = separator.join(items)

        # Truncate by words if over budget
        if not self.fits(combined):
            words = combined.split()
            # Target word count = max_tokens * 0.75 (inverse of estimate)
            target_words = int(self._max_tokens * 0.75)
            combined = " ".join(words[:target_words])

        content = combined
        # Count dropped: items whose content does not appear in the final string
        present = 0
        for item in items:
            if item in content:
                present += 1

        return CompressedContext(
            original_length=original_length,
            compressed_length=self.estimate_tokens(content),
            strategy_used=CompressionStrategy.SUMMARIZE,
            content=content,
            dropped_count=len(items) - present,
        )

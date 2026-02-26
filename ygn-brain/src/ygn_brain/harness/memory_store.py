"""Memory store for capitalizing harness patterns."""

from __future__ import annotations

from ygn_brain.harness.types import Candidate, Feedback
from ygn_brain.memory import MemoryCategory
from ygn_brain.tiered_memory import MemoryTier, TieredMemoryService


class HarnessMemoryStore:
    """Stores winning patterns for reuse in future runs.

    Wraps :class:`TieredMemoryService` to persist harness results in the
    COLD tier so that successful provider/model/prompt combinations can be
    recalled across sessions.
    """

    def __init__(self, memory: TieredMemoryService | None = None) -> None:
        self._memory = memory or TieredMemoryService()

    def store_pattern(
        self,
        task: str,
        candidate: Candidate,
        feedback: Feedback,
    ) -> None:
        """Persist a winning candidate pattern in cold-tier memory."""
        key = f"harness:{candidate.id}"
        content = (
            f"task: {task}\n"
            f"provider: {candidate.provider}\n"
            f"model: {candidate.model}\n"
            f"score: {feedback.score}\n"
            f"prompt: {candidate.prompt[:200]}"
        )
        self._memory.store(
            key,
            content,
            MemoryCategory.CORE,
            "harness",
            tier=MemoryTier.COLD,
        )

    def recall_patterns(self, task: str, limit: int = 3) -> list[dict]:
        """Recall stored patterns matching *task* (word-overlap search).

        Returns a list of dicts with keys: task, provider, model, score, prompt.
        """
        results = self._memory.recall(task, limit=limit)
        patterns: list[dict] = []
        for r in results:
            if r.key.startswith("harness:"):
                lines = r.content.split("\n")
                pattern: dict = {}
                for line in lines:
                    if ": " in line:
                        k, v = line.split(": ", 1)
                        pattern[k] = float(v) if k == "score" else v
                patterns.append(pattern)
        return patterns

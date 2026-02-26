"""Candidate selection strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ygn_brain.harness.types import Candidate, Feedback


class Selector(ABC):
    """Pick the best candidate from a scored pool."""

    @abstractmethod
    def select(self, candidates: list[tuple[Candidate, Feedback]]) -> Candidate:
        """Return the winning candidate."""


class ConsensusSelector(Selector):
    """Select by score + consensus bonus.

    Candidates whose normalised output matches at least one other
    candidate receive *consensus_bonus* added to their feedback score.
    Ties are broken by lower latency.
    """

    def __init__(self, consensus_bonus: float = 0.15) -> None:
        self._bonus = consensus_bonus

    def select(self, candidates: list[tuple[Candidate, Feedback]]) -> Candidate:
        if not candidates:
            raise ValueError("No candidates")

        # Group by normalised output (first 200 chars, stripped, lowered)
        output_groups: dict[str, list[str]] = {}
        for c, _ in candidates:
            key = c.output.strip().lower()[:200]
            output_groups.setdefault(key, []).append(c.id)

        consensus_ids: set[str] = set()
        for ids in output_groups.values():
            if len(ids) >= 2:
                consensus_ids.update(ids)

        scored: list[tuple[float, float, Candidate]] = []
        for c, f in candidates:
            effective = f.score + (self._bonus if c.id in consensus_ids else 0.0)
            scored.append((effective, -c.latency_ms, c))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return scored[0][2]

"""Refinement policies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ygn_brain.harness.types import Feedback


class RefinementPolicy(ABC):
    """Controls when to stop refining and how to adjust prompts."""

    @abstractmethod
    def should_continue(self, round_num: int, best_score: float, history: list[Feedback]) -> bool:
        """Return True if another refinement round should run."""

    @abstractmethod
    def refine_prompt(self, task: str, feedback: Feedback) -> str:
        """Return an improved prompt incorporating feedback diagnostics."""


class DefaultPolicy(RefinementPolicy):
    """Stop after *max_rounds* or once *min_score* is reached."""

    def __init__(self, max_rounds: int = 3, min_score: float = 0.8) -> None:
        self._max_rounds = max_rounds
        self._min_score = min_score

    def should_continue(self, round_num: int, best_score: float, history: list[Feedback]) -> bool:
        return round_num < self._max_rounds and best_score < self._min_score

    def refine_prompt(self, task: str, feedback: Feedback) -> str:
        return (
            f"{task}\n\n"
            f"Previous attempt feedback: {feedback.diagnostics}\n"
            f"Score: {feedback.score:.2f}. Please improve."
        )

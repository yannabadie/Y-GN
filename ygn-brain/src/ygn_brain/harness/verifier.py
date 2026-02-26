"""Verification backends for the Refinement Harness."""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod

from ygn_brain.harness.types import Candidate, Feedback

_REFUSAL_PATTERNS = [
    "i cannot",
    "i can't",
    "i'm unable",
    "i am unable",
    "i apologize",
    "as an ai",
    "i don't have access",
]


class Verifier(ABC):
    """Abstract base for candidate verification."""

    @abstractmethod
    def verify(self, candidate: Candidate, task: str) -> Feedback:
        """Verify a candidate output against the task."""


class TextVerifier(Verifier):
    """Heuristic text quality verifier."""

    def __init__(self, min_length: int = 20) -> None:
        self._min_length = min_length

    def verify(self, candidate: Candidate, task: str) -> Feedback:
        text = candidate.output.strip()
        if not text:
            return Feedback(passed=False, score=0.0, diagnostics="Empty output")

        score = 0.0
        diagnostics: list[str] = []

        # Length score (0-0.3)
        score += min(len(text) / 200.0, 0.3)

        # Refusal check (0 or 0.3)
        lower = text.lower()
        is_refusal = any(p in lower for p in _REFUSAL_PATTERNS)
        if is_refusal:
            diagnostics.append("Detected refusal pattern")
        else:
            score += 0.3

        # Relevance (0-0.2)
        task_words = set(task.lower().split())
        output_words = set(lower.split())
        overlap = len(task_words & output_words) / max(len(task_words), 1)
        score += min(overlap, 0.2)

        # Structure (0-0.2)
        if any(c in text for c in ["\n", "- ", "1.", "```", "##"]):
            score += 0.2

        passed = score >= 0.5 and not is_refusal
        return Feedback(
            passed=passed,
            score=round(score, 3),
            diagnostics="; ".join(diagnostics) if diagnostics else "ok",
        )


class CommandVerifier(Verifier):
    """Runs a shell command. Score 1.0 if exit 0, 0.0 otherwise."""

    def __init__(self, command: str, timeout: float = 60.0) -> None:
        self._command = command
        self._timeout = timeout

    def verify(self, candidate: Candidate, task: str) -> Feedback:
        try:
            result = subprocess.run(  # noqa: S602
                self._command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            passed = result.returncode == 0
            return Feedback(
                passed=passed,
                score=1.0 if passed else 0.0,
                diagnostics=f"exit code {result.returncode}",
                artifacts={
                    "stdout": result.stdout[:2000],
                    "stderr": result.stderr[:2000],
                },
            )
        except subprocess.TimeoutExpired:
            return Feedback(
                passed=False,
                score=0.0,
                diagnostics=f"Timed out after {self._timeout}s",
            )

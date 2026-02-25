"""Guard backends — ML-based classifier stubs.

This module provides the foundation for ML-based guard backends such as
PromptGuard 2 or LlamaFirewall. The ``ClassifierGuard`` ABC defines the
interface; ``StubClassifierGuard`` is a safe pass-through for testing.

Integration path for LlamaFirewall:
  1. ``pip install llamafirewall``
  2. Subclass ``ClassifierGuard``
  3. Implement ``classify()`` using LlamaFirewall's scanner
  4. Register in ``GuardPipeline``
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .guard import GuardBackend, GuardResult, ThreatLevel


class ClassifierGuard(GuardBackend, ABC):
    """ABC for ML-based classifier guard backends."""

    @abstractmethod
    def classify(self, text: str) -> tuple[bool, float]:
        """Classify text as safe or unsafe.

        Returns:
            (is_safe, threat_score) where threat_score is 0.0-100.0.
        """

    def check(self, text: str) -> GuardResult:
        is_safe, score = self.classify(text)
        if is_safe:
            return GuardResult(
                allowed=True,
                threat_level=ThreatLevel.NONE,
                reason=f"{self.name()}: safe (score={score:.1f})",
                score=score,
            )
        threat = ThreatLevel.CRITICAL if score >= 75.0 else ThreatLevel.HIGH  # noqa: PLR2004
        return GuardResult(
            allowed=False,
            threat_level=threat,
            reason=f"{self.name()}: unsafe (score={score:.1f})",
            score=score,
        )


class StubClassifierGuard(ClassifierGuard):
    """Always-passing stub for testing."""

    def classify(self, text: str) -> tuple[bool, float]:
        return (True, 0.0)

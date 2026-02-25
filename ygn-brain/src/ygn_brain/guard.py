"""Security guard pipeline — input validation and threat detection.

v0.3.0: GuardBackend ABC, scoring, ToolInvocationGuard.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum


class ThreatLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_THREAT_SCORES: dict[ThreatLevel, float] = {
    ThreatLevel.NONE: 0.0,
    ThreatLevel.LOW: 25.0,
    ThreatLevel.MEDIUM: 50.0,
    ThreatLevel.HIGH: 75.0,
    ThreatLevel.CRITICAL: 100.0,
}


@dataclass(frozen=True)
class GuardResult:
    """Result of a guard check."""

    allowed: bool
    threat_level: ThreatLevel
    reason: str
    score: float = 0.0


# ---------------------------------------------------------------------------
# GuardBackend ABC
# ---------------------------------------------------------------------------


class GuardBackend(ABC):
    """Abstract base class for guard backends."""

    @abstractmethod
    def check(self, text: str) -> GuardResult: ...

    def name(self) -> str:
        return type(self).__name__


# ---------------------------------------------------------------------------
# Regex-based guard (formerly InputGuard)
# ---------------------------------------------------------------------------

_INSTRUCTION_OVERRIDE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules)", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+(instructions|rules)", re.I),
    re.compile(r"forget\s+(all\s+)?(previous|prior)\s+(instructions|rules|context)", re.I),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+\w+", re.I),
    re.compile(r"new\s+instructions?:", re.I),
]

_ROLE_MANIPULATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bsystem\s*:\s*", re.I),
    re.compile(r"\bassistant\s*:\s*", re.I),
    re.compile(r"\b(?:act|behave|pretend)\s+as\s+(?:if\s+you\s+are|a)\b", re.I),
    re.compile(r"you\s+must\s+obey", re.I),
]

_DELIMITER_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"```\s*system", re.I),
    re.compile(r"<\|(?:im_start|im_end|system|endoftext)\|>", re.I),
    re.compile(r"###\s*(?:SYSTEM|INSTRUCTION)", re.I),
    re.compile(r"\[INST\]", re.I),
]


class RegexGuard(GuardBackend):
    """Validates user input against prompt-injection patterns."""

    def check(self, text: str) -> GuardResult:
        """Run all pattern checks and return the highest-severity match."""
        for pat in _INSTRUCTION_OVERRIDE_PATTERNS:
            if pat.search(text):
                return GuardResult(
                    allowed=False,
                    threat_level=ThreatLevel.HIGH,
                    reason=f"Instruction override detected: {pat.pattern}",
                    score=_THREAT_SCORES[ThreatLevel.HIGH],
                )

        for pat in _ROLE_MANIPULATION_PATTERNS:
            if pat.search(text):
                return GuardResult(
                    allowed=False,
                    threat_level=ThreatLevel.HIGH,
                    reason=f"Role manipulation detected: {pat.pattern}",
                    score=_THREAT_SCORES[ThreatLevel.HIGH],
                )

        for pat in _DELIMITER_INJECTION_PATTERNS:
            if pat.search(text):
                return GuardResult(
                    allowed=False,
                    threat_level=ThreatLevel.CRITICAL,
                    reason=f"Delimiter injection detected: {pat.pattern}",
                    score=_THREAT_SCORES[ThreatLevel.CRITICAL],
                )

        return GuardResult(
            allowed=True,
            threat_level=ThreatLevel.NONE,
            reason="Input passed all checks",
            score=0.0,
        )


# Backward compatibility alias
InputGuard = RegexGuard


# ---------------------------------------------------------------------------
# Tool invocation guard
# ---------------------------------------------------------------------------


@dataclass
class ToolInvocationGuard(GuardBackend):
    """Guards tool invocations: whitelist, rate limit, Log-To-Leak detection."""

    allowed_tools: set[str] = field(default_factory=set)
    max_calls_per_session: int = 10
    _call_count: int = field(default=0, init=False, repr=False)
    _prior_messages: list[str] = field(default_factory=list, init=False, repr=False)

    def record_message(self, text: str) -> None:
        """Record a user/assistant message for Log-To-Leak detection."""
        self._prior_messages.append(text)

    def check(self, text: str) -> GuardResult:
        """Check a tool invocation string: 'tool_name:arguments'."""
        parts = text.split(":", 1)
        tool_name = parts[0].strip()
        tool_args = parts[1].strip() if len(parts) > 1 else ""

        # Unknown tool check
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return GuardResult(
                allowed=False,
                threat_level=ThreatLevel.CRITICAL,
                reason=f"Unknown tool: {tool_name}",
                score=_THREAT_SCORES[ThreatLevel.CRITICAL],
            )

        # Rate limit check
        self._call_count += 1
        if self._call_count > self.max_calls_per_session:
            return GuardResult(
                allowed=False,
                threat_level=ThreatLevel.HIGH,
                reason=f"Rate limit exceeded: {self._call_count}/{self.max_calls_per_session}",
                score=_THREAT_SCORES[ThreatLevel.HIGH],
            )

        # Log-To-Leak detection: tool args contain content from prior messages
        if tool_args and self._prior_messages:
            for msg in self._prior_messages:
                if len(msg) > 20 and msg in tool_args:  # noqa: PLR2004
                    return GuardResult(
                        allowed=False,
                        threat_level=ThreatLevel.HIGH,
                        reason="Log-To-Leak: tool arguments contain prior message content",
                        score=_THREAT_SCORES[ThreatLevel.HIGH],
                    )

        return GuardResult(
            allowed=True,
            threat_level=ThreatLevel.NONE,
            reason="Tool invocation passed all checks",
            score=0.0,
        )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class GuardPipeline:
    """Composes multiple guards; returns first blocking result."""

    def __init__(self, guards: list[GuardBackend] | None = None) -> None:
        self._guards: list[GuardBackend] = guards if guards is not None else [RegexGuard()]

    def add_guard(self, guard: GuardBackend) -> None:
        self._guards.append(guard)

    def evaluate(self, text: str) -> GuardResult:
        """Run all guards in order; return first blocking result or pass with max score."""
        max_score = 0.0
        for guard in self._guards:
            result = guard.check(text)
            max_score = max(max_score, result.score)
            if not result.allowed:
                return result
        return GuardResult(
            allowed=True,
            threat_level=ThreatLevel.NONE,
            reason="All guards passed",
            score=max_score,
        )

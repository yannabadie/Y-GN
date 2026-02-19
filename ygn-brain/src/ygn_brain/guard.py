"""Security guard pipeline — input validation and threat detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ThreatLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class GuardResult:
    """Result of a guard check."""

    allowed: bool
    threat_level: ThreatLevel
    reason: str


# ---------------------------------------------------------------------------
# Individual guard checks
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


class InputGuard:
    """Validates user input against prompt-injection patterns."""

    def check(self, text: str) -> GuardResult:
        """Run all pattern checks and return the highest-severity match."""
        # Check instruction overrides (HIGH)
        for pat in _INSTRUCTION_OVERRIDE_PATTERNS:
            if pat.search(text):
                return GuardResult(
                    allowed=False,
                    threat_level=ThreatLevel.HIGH,
                    reason=f"Instruction override detected: {pat.pattern}",
                )

        # Check role manipulation (HIGH)
        for pat in _ROLE_MANIPULATION_PATTERNS:
            if pat.search(text):
                return GuardResult(
                    allowed=False,
                    threat_level=ThreatLevel.HIGH,
                    reason=f"Role manipulation detected: {pat.pattern}",
                )

        # Check delimiter injection (CRITICAL)
        for pat in _DELIMITER_INJECTION_PATTERNS:
            if pat.search(text):
                return GuardResult(
                    allowed=False,
                    threat_level=ThreatLevel.CRITICAL,
                    reason=f"Delimiter injection detected: {pat.pattern}",
                )

        return GuardResult(
            allowed=True,
            threat_level=ThreatLevel.NONE,
            reason="Input passed all checks",
        )


class GuardPipeline:
    """Composes multiple guards; returns first blocking result."""

    def __init__(self, guards: list[InputGuard] | None = None) -> None:
        self._guards: list[InputGuard] = guards if guards is not None else [InputGuard()]

    def add_guard(self, guard: InputGuard) -> None:
        self._guards.append(guard)

    def evaluate(self, text: str) -> GuardResult:
        """Run all guards in order; return first blocking result or pass."""
        for guard in self._guards:
            result = guard.check(text)
            if not result.allowed:
                return result
        return GuardResult(
            allowed=True,
            threat_level=ThreatLevel.NONE,
            reason="All guards passed",
        )

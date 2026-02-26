"""Core types for the Refinement Harness."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Candidate:
    """A single candidate output from a provider."""

    id: str
    provider: str
    model: str
    prompt: str
    output: str
    latency_ms: float
    token_count: int


@dataclass
class Feedback:
    """Verification result for a candidate."""

    passed: bool
    score: float  # 0.0 - 1.0
    diagnostics: str
    artifacts: dict = field(default_factory=dict)


@dataclass
class HarnessConfig:
    """Configuration for a refinement harness run."""

    max_rounds: int = 3
    min_score: float = 0.8
    ensemble: bool = True
    providers: list[str] = field(default_factory=lambda: ["codex", "gemini"])
    candidates_per_provider: int = 2
    verifier: str = "text"
    command: str | None = None


@dataclass
class HarnessResult:
    """Result of a complete harness run."""

    winner: Candidate
    feedback: Feedback
    rounds_used: int
    total_candidates: int


POETIQ_PRESET = HarnessConfig(
    max_rounds=3,
    min_score=0.8,
    ensemble=True,
    providers=["gemini", "codex"],
    candidates_per_provider=2,
    verifier="text",
)

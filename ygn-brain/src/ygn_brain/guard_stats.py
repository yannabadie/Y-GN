"""Guard statistics tracking."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ygn_brain.guard import GuardResult


@dataclass
class GuardStats:
    """Tracks guard check statistics for reporting."""

    total_checks: int = 0
    blocked: int = 0
    threat_counts: dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    total_latency_ms: float = 0.0

    def record(self, result: GuardResult, latency_ms: float = 0.0) -> None:
        self.total_checks += 1
        if not result.allowed:
            self.blocked += 1
        self.threat_counts[result.threat_level.name] += 1
        self.total_latency_ms += latency_ms

    def summary(self) -> dict:
        avg_latency = (
            self.total_latency_ms / self.total_checks
            if self.total_checks > 0
            else 0.0
        )
        return {
            "total_checks": self.total_checks,
            "blocked": self.blocked,
            "threat_levels": dict(self.threat_counts),
            "avg_latency_ms": round(avg_latency, 2),
        }

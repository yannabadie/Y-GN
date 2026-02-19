"""DyLAN Metrics — Dynamic LLM-Agent Network performance tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class AgentMetrics:
    """Aggregated performance metrics for a single agent."""

    agent_id: str
    total_tasks: int = 0
    successes: int = 0
    failures: int = 0
    avg_latency_ms: float = 0.0
    domain_scores: dict[str, float] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)


@dataclass
class _TaskRecord:
    """Internal record for a single task execution."""

    domain: str
    success: bool
    latency_ms: float
    timestamp: float = field(default_factory=time.time)


class DyLANTracker:
    """Tracks agent performance across domains for dynamic agent selection."""

    def __init__(self) -> None:
        self._records: dict[str, list[_TaskRecord]] = {}

    def record_task(
        self,
        agent_id: str,
        domain: str,
        success: bool,  # noqa: FBT001
        latency_ms: float,
    ) -> None:
        """Record a task result for an agent."""
        if agent_id not in self._records:
            self._records[agent_id] = []
        self._records[agent_id].append(
            _TaskRecord(domain=domain, success=success, latency_ms=latency_ms)
        )

    def get_metrics(self, agent_id: str) -> AgentMetrics:
        """Compute and return current metrics for an agent."""
        records = self._records.get(agent_id, [])
        if not records:
            return AgentMetrics(agent_id=agent_id)

        total = len(records)
        successes = sum(1 for r in records if r.success)
        failures = total - successes
        avg_latency = sum(r.latency_ms for r in records) / total

        # Compute per-domain scores
        domain_counts: dict[str, tuple[int, int]] = {}  # domain -> (successes, total)
        for r in records:
            s, t = domain_counts.get(r.domain, (0, 0))
            t += 1
            if r.success:
                s += 1
            domain_counts[r.domain] = (s, t)

        domain_scores: dict[str, float] = {}
        for domain, (s, t) in domain_counts.items():
            domain_scores[domain] = s / t if t > 0 else 0.0

        last_updated = max(r.timestamp for r in records)

        return AgentMetrics(
            agent_id=agent_id,
            total_tasks=total,
            successes=successes,
            failures=failures,
            avg_latency_ms=avg_latency,
            domain_scores=domain_scores,
            last_updated=last_updated,
        )

    def rank_agents(self, domain: str | None = None) -> list[tuple[str, float]]:
        """Return agents sorted by success rate (descending).

        If *domain* is given, rank by domain-specific success rate.
        """
        rankings: list[tuple[str, float]] = []
        for agent_id in self._records:
            metrics = self.get_metrics(agent_id)
            if domain is not None:
                score = metrics.domain_scores.get(domain, 0.0)
            else:
                score = metrics.successes / metrics.total_tasks if metrics.total_tasks > 0 else 0.0
            rankings.append((agent_id, score))
        rankings.sort(key=lambda t: t[1], reverse=True)
        return rankings

    def best_agent_for(self, domain: str) -> str | None:
        """Return the agent_id with the highest score in the given domain."""
        rankings = self.rank_agents(domain=domain)
        if not rankings:
            return None
        # Only return an agent that actually has records in this domain
        for agent_id, _score in rankings:
            metrics = self.get_metrics(agent_id)
            if domain in metrics.domain_scores:
                return agent_id
        return None

    def prune_inactive(self, max_staleness_seconds: float = 3600.0) -> int:
        """Remove agents whose last task is older than *max_staleness_seconds*."""
        now = time.time()
        stale: list[str] = []
        for agent_id, records in self._records.items():
            if not records:
                stale.append(agent_id)
                continue
            last_ts = max(r.timestamp for r in records)
            if (now - last_ts) >= max_staleness_seconds:
                stale.append(agent_id)
        for agent_id in stale:
            del self._records[agent_id]
        return len(stale)

    def all_agents(self) -> list[str]:
        """Return a list of all tracked agent IDs."""
        return list(self._records.keys())

"""SuccessMemory — track task outcomes to guide future swarm-mode selection."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SuccessRecord:
    """A single recorded task outcome."""

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    task_description: str = ""
    swarm_mode: str = ""
    domains: list[str] = field(default_factory=list)
    complexity: str = ""
    outcome: str = ""  # "success" or "failure"
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class SuccessMemory:
    """Records task outcomes and provides lookup for optimal swarm modes."""

    def __init__(self) -> None:
        self._records: list[SuccessRecord] = []

    def record(
        self,
        task_desc: str,
        mode: str,
        domains: list[str],
        complexity: str,
        outcome: str,
        confidence: float,
    ) -> SuccessRecord:
        """Record a task outcome and return the created record."""
        rec = SuccessRecord(
            task_description=task_desc,
            swarm_mode=mode,
            domains=list(domains),
            complexity=complexity,
            outcome=outcome,
            confidence=confidence,
        )
        self._records.append(rec)
        return rec

    def query(
        self,
        domains: list[str] | None = None,
        complexity: str | None = None,
        limit: int = 10,
    ) -> list[SuccessRecord]:
        """Return matching records sorted by confidence descending."""
        results: list[SuccessRecord] = []
        for rec in self._records:
            if domains is not None:
                domain_set = set(domains)
                if not domain_set.intersection(rec.domains):
                    continue
            if complexity is not None and rec.complexity != complexity:
                continue
            results.append(rec)
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results[:limit]

    def best_mode_for(self, domains: list[str], complexity: str) -> str | None:
        """Return the swarm mode with the highest success rate for similar tasks.

        Only considers records matching at least one of the given domains *and*
        the specified complexity.  Returns ``None`` if no matching records exist.
        """
        matching = self.query(domains=domains, complexity=complexity, limit=999)
        if not matching:
            return None

        # Group by mode, compute success rate
        mode_stats: dict[str, tuple[int, int]] = {}  # mode -> (successes, total)
        for rec in matching:
            successes, total = mode_stats.get(rec.swarm_mode, (0, 0))
            total += 1
            if rec.outcome == "success":
                successes += 1
            mode_stats[rec.swarm_mode] = (successes, total)

        best_mode: str | None = None
        best_rate = -1.0
        for mode, (successes, total) in mode_stats.items():
            rate = successes / total if total > 0 else 0.0
            if rate > best_rate:
                best_rate = rate
                best_mode = mode
        return best_mode

    def success_rate(self, mode: str) -> float:
        """Return the overall success rate for a given swarm mode."""
        total = 0
        successes = 0
        for rec in self._records:
            if rec.swarm_mode == mode:
                total += 1
                if rec.outcome == "success":
                    successes += 1
        if total == 0:
            return 0.0
        return successes / total

    def clear(self) -> int:
        """Remove all records. Returns the number removed."""
        count = len(self._records)
        self._records.clear()
        return count

"""Tests for guard statistics tracking."""

from ygn_brain.guard import GuardResult, ThreatLevel
from ygn_brain.guard_stats import GuardStats


def test_guard_stats_empty():
    stats = GuardStats()
    summary = stats.summary()
    assert summary["total_checks"] == 0
    assert summary["blocked"] == 0


def test_guard_stats_record():
    stats = GuardStats()
    stats.record(GuardResult(
        allowed=True,
        threat_level=ThreatLevel.NONE,
        reason="ok",
        score=0.0,
    ))
    stats.record(GuardResult(
        allowed=False,
        threat_level=ThreatLevel.HIGH,
        reason="blocked",
        score=80.0,
    ))
    summary = stats.summary()
    assert summary["total_checks"] == 2
    assert summary["blocked"] == 1
    assert summary["threat_levels"]["NONE"] == 1
    assert summary["threat_levels"]["HIGH"] == 1

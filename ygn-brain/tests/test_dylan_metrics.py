"""Tests for DyLAN metrics — agent tracking, ranking, pruning."""

import time

from ygn_brain.dylan_metrics import DyLANTracker


def test_record_and_get_metrics():
    """Recording tasks and retrieving metrics works correctly."""
    tracker = DyLANTracker()
    tracker.record_task("agent-1", "code", success=True, latency_ms=100.0)
    tracker.record_task("agent-1", "code", success=True, latency_ms=200.0)
    tracker.record_task("agent-1", "code", success=False, latency_ms=150.0)

    metrics = tracker.get_metrics("agent-1")
    assert metrics.agent_id == "agent-1"
    assert metrics.total_tasks == 3
    assert metrics.successes == 2
    assert metrics.failures == 1
    assert abs(metrics.avg_latency_ms - 150.0) < 1e-9
    assert "code" in metrics.domain_scores
    assert abs(metrics.domain_scores["code"] - 2.0 / 3.0) < 1e-9


def test_rank_agents_overall():
    """rank_agents returns agents sorted by overall success rate."""
    tracker = DyLANTracker()
    # agent-a: 100% success
    tracker.record_task("agent-a", "code", success=True, latency_ms=50.0)
    # agent-b: 50% success
    tracker.record_task("agent-b", "code", success=True, latency_ms=50.0)
    tracker.record_task("agent-b", "code", success=False, latency_ms=50.0)

    rankings = tracker.rank_agents()
    assert rankings[0][0] == "agent-a"
    assert rankings[0][1] == 1.0
    assert rankings[1][0] == "agent-b"
    assert rankings[1][1] == 0.5


def test_rank_agents_by_domain():
    """rank_agents filters by domain when specified."""
    tracker = DyLANTracker()
    # agent-a: good at code, bad at math
    tracker.record_task("agent-a", "code", success=True, latency_ms=50.0)
    tracker.record_task("agent-a", "math", success=False, latency_ms=50.0)
    # agent-b: good at math
    tracker.record_task("agent-b", "math", success=True, latency_ms=50.0)

    math_rankings = tracker.rank_agents(domain="math")
    assert math_rankings[0][0] == "agent-b"
    assert math_rankings[0][1] == 1.0


def test_best_agent_for_domain():
    """best_agent_for returns the top agent in a specific domain."""
    tracker = DyLANTracker()
    tracker.record_task("agent-a", "code", success=True, latency_ms=50.0)
    tracker.record_task("agent-b", "code", success=True, latency_ms=50.0)
    tracker.record_task("agent-b", "code", success=True, latency_ms=50.0)
    tracker.record_task("agent-a", "code", success=False, latency_ms=50.0)

    best = tracker.best_agent_for("code")
    assert best == "agent-b"  # 100% vs 50%


def test_best_agent_for_unknown_domain():
    """best_agent_for returns None when no agent has records in the domain."""
    tracker = DyLANTracker()
    tracker.record_task("agent-a", "code", success=True, latency_ms=50.0)
    assert tracker.best_agent_for("cooking") is None


def test_prune_inactive():
    """prune_inactive removes agents with stale records."""
    tracker = DyLANTracker()
    tracker.record_task("agent-old", "code", success=True, latency_ms=50.0)
    # Manually backdate the record
    tracker._records["agent-old"][0].timestamp = time.time() - 7200  # 2 hours ago

    tracker.record_task("agent-fresh", "code", success=True, latency_ms=50.0)

    pruned = tracker.prune_inactive(max_staleness_seconds=3600.0)
    assert pruned == 1
    assert "agent-old" not in tracker.all_agents()
    assert "agent-fresh" in tracker.all_agents()


def test_multiple_domains():
    """An agent can have scores across multiple domains."""
    tracker = DyLANTracker()
    tracker.record_task("agent-multi", "code", success=True, latency_ms=50.0)
    tracker.record_task("agent-multi", "math", success=False, latency_ms=100.0)
    tracker.record_task("agent-multi", "writing", success=True, latency_ms=75.0)

    metrics = tracker.get_metrics("agent-multi")
    assert set(metrics.domain_scores.keys()) == {"code", "math", "writing"}
    assert metrics.domain_scores["code"] == 1.0
    assert metrics.domain_scores["math"] == 0.0
    assert metrics.domain_scores["writing"] == 1.0


def test_empty_tracker():
    """Operations on an empty tracker return sensible defaults."""
    tracker = DyLANTracker()
    assert tracker.all_agents() == []
    assert tracker.rank_agents() == []
    assert tracker.best_agent_for("code") is None
    metrics = tracker.get_metrics("nonexistent")
    assert metrics.total_tasks == 0
    assert metrics.successes == 0


def test_all_agents():
    """all_agents returns all tracked agent IDs."""
    tracker = DyLANTracker()
    tracker.record_task("a", "code", success=True, latency_ms=50.0)
    tracker.record_task("b", "math", success=True, latency_ms=50.0)
    tracker.record_task("c", "writing", success=True, latency_ms=50.0)

    agents = tracker.all_agents()
    assert set(agents) == {"a", "b", "c"}

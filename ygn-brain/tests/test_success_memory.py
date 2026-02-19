"""Tests for success memory — record, query, best_mode_for, success_rate."""

from ygn_brain.success_memory import SuccessMemory


def test_record_and_query():
    """Recording a task outcome and querying it back works."""
    mem = SuccessMemory()
    rec = mem.record(
        task_desc="Write unit tests",
        mode="sequential",
        domains=["code"],
        complexity="moderate",
        outcome="success",
        confidence=0.9,
    )
    assert rec.record_id
    assert rec.task_description == "Write unit tests"

    results = mem.query()
    assert len(results) == 1
    assert results[0].record_id == rec.record_id


def test_query_sorted_by_confidence():
    """Query returns records sorted by confidence descending."""
    mem = SuccessMemory()
    mem.record("low", "parallel", ["code"], "simple", "success", 0.3)
    mem.record("high", "sequential", ["code"], "simple", "success", 0.95)
    mem.record("mid", "specialist", ["code"], "simple", "success", 0.7)

    results = mem.query()
    confidences = [r.confidence for r in results]
    assert confidences == sorted(confidences, reverse=True)


def test_best_mode_for():
    """best_mode_for returns the mode with highest success rate."""
    mem = SuccessMemory()
    # Parallel: 2 successes, 1 failure => 66%
    mem.record("t1", "parallel", ["code"], "complex", "success", 0.8)
    mem.record("t2", "parallel", ["code"], "complex", "success", 0.7)
    mem.record("t3", "parallel", ["code"], "complex", "failure", 0.4)
    # Sequential: 1 success => 100%
    mem.record("t4", "sequential", ["code"], "complex", "success", 0.9)

    best = mem.best_mode_for(domains=["code"], complexity="complex")
    assert best == "sequential"


def test_success_rate():
    """success_rate returns correct ratio."""
    mem = SuccessMemory()
    mem.record("t1", "parallel", ["code"], "simple", "success", 0.8)
    mem.record("t2", "parallel", ["code"], "simple", "failure", 0.3)
    mem.record("t3", "parallel", ["code"], "simple", "success", 0.9)

    rate = mem.success_rate("parallel")
    assert abs(rate - 2.0 / 3.0) < 1e-9


def test_success_rate_unknown_mode():
    """success_rate for unknown mode returns 0.0."""
    mem = SuccessMemory()
    assert mem.success_rate("nonexistent") == 0.0


def test_filter_by_domain():
    """Query filters by domain correctly."""
    mem = SuccessMemory()
    mem.record("code task", "sequential", ["code"], "simple", "success", 0.8)
    mem.record("math task", "parallel", ["math"], "simple", "success", 0.9)
    mem.record("mixed task", "specialist", ["code", "math"], "complex", "success", 0.7)

    code_results = mem.query(domains=["code"])
    assert len(code_results) == 2  # "code task" + "mixed task"
    for r in code_results:
        assert "code" in r.domains


def test_filter_by_complexity():
    """Query filters by complexity correctly."""
    mem = SuccessMemory()
    mem.record("easy", "sequential", ["code"], "simple", "success", 0.8)
    mem.record("hard", "parallel", ["code"], "complex", "success", 0.9)

    simple_results = mem.query(complexity="simple")
    assert len(simple_results) == 1
    assert simple_results[0].complexity == "simple"


def test_empty_memory():
    """Operations on empty memory return sensible defaults."""
    mem = SuccessMemory()
    assert mem.query() == []
    assert mem.best_mode_for(["code"], "simple") is None
    assert mem.success_rate("any") == 0.0
    assert mem.clear() == 0


def test_clear():
    """Clear removes all records and returns count."""
    mem = SuccessMemory()
    mem.record("t1", "parallel", ["code"], "simple", "success", 0.8)
    mem.record("t2", "sequential", ["math"], "complex", "success", 0.9)

    count = mem.clear()
    assert count == 2
    assert mem.query() == []

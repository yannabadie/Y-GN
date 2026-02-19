"""Tests for swarm module — hybrid swarm engine."""

from ygn_brain.swarm import (
    SwarmEngine,
    SwarmMode,
    TaskAnalyzer,
    TaskComplexity,
)


def test_trivial_task_analysis():
    analyzer = TaskAnalyzer()
    result = analyzer.analyze("hello")
    assert result.complexity == TaskComplexity.TRIVIAL
    assert result.suggested_mode == SwarmMode.SEQUENTIAL


def test_expert_task_analysis():
    analyzer = TaskAnalyzer()
    query = (
        "Research the latest machine learning papers, write a summary, "
        "and implement a code prototype using the data from the CSV dataset "
        "with a proper design architecture"
    )
    result = analyzer.analyze(query)
    assert result.complexity == TaskComplexity.EXPERT
    assert len(result.domains) >= 3
    assert result.suggested_mode == SwarmMode.SPECIALIST


def test_engine_routes_to_sequential():
    engine = SwarmEngine()
    result = engine.run("hi")
    assert result.mode == SwarmMode.SEQUENTIAL
    assert "hi" in result.output


def test_engine_routes_to_specialist():
    engine = SwarmEngine()
    query = (
        "Research and analyze the data from multiple datasets, "
        "write a detailed code implementation with proper design, "
        "and calculate performance math metrics"
    )
    result = engine.run(query)
    assert result.mode == SwarmMode.SPECIALIST
    assert "specialist" in result.output


def test_engine_analyze_returns_task_analysis():
    engine = SwarmEngine()
    analysis = engine.analyze("Write a short essay about cats")
    assert analysis.complexity in TaskComplexity
    assert len(analysis.domains) >= 1

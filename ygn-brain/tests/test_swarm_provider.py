"""Tests for SwarmEngine.execute_with_provider — LLM-backed swarm execution."""

from __future__ import annotations

import pytest

from ygn_brain.evidence import EvidencePack
from ygn_brain.guard import GuardPipeline, RegexGuard
from ygn_brain.provider import StubLLMProvider
from ygn_brain.swarm import (
    RedBlueExecutor,
    SwarmEngine,
    SwarmMode,
    SwarmResult,
    TaskComplexity,
)

# ---------------------------------------------------------------------------
# Parallel mode
# ---------------------------------------------------------------------------


# A task that triggers exactly 2 domains (research + code) and COMPLEX complexity -> PARALLEL
_PARALLEL_TASK = (
    "Investigate the performance of this function and refactor it to be more efficient"
)


@pytest.mark.asyncio
async def test_parallel_mode_returns_parallel_result():
    """A complex multi-domain task should route to parallel and produce combined output."""
    engine = SwarmEngine()
    provider = StubLLMProvider()
    analysis = engine.analyze(_PARALLEL_TASK)
    assert len(analysis.domains) == 2
    assert analysis.complexity == TaskComplexity.COMPLEX
    assert analysis.suggested_mode == SwarmMode.PARALLEL

    result = await engine.execute_with_provider(_PARALLEL_TASK, provider)
    assert isinstance(result, SwarmResult)
    assert result.mode == SwarmMode.PARALLEL
    assert result.metadata["strategy"] == "fan-out-fan-in"
    assert result.metadata["agents"] >= 2


@pytest.mark.asyncio
async def test_parallel_mode_combines_domain_outputs():
    """Parallel mode should produce output containing separator between domain results."""
    engine = SwarmEngine()
    provider = StubLLMProvider()
    result = await engine.execute_with_provider(_PARALLEL_TASK, provider)
    # Multiple domains should produce output with separator
    assert "---" in result.output
    # Stub provider includes "stub response" in each response
    assert "stub response" in result.output


@pytest.mark.asyncio
async def test_parallel_mode_domains_in_metadata():
    """Parallel metadata should list the detected domains."""
    engine = SwarmEngine()
    provider = StubLLMProvider()
    result = await engine.execute_with_provider(_PARALLEL_TASK, provider)
    assert "domains" in result.metadata
    assert len(result.metadata["domains"]) >= 2


# ---------------------------------------------------------------------------
# Sequential mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sequential_mode_returns_sequential_result():
    """A trivial/simple task should route to sequential mode."""
    engine = SwarmEngine()
    provider = StubLLMProvider()
    task = "hello"
    analysis = engine.analyze(task)
    assert analysis.suggested_mode == SwarmMode.SEQUENTIAL

    result = await engine.execute_with_provider(task, provider)
    assert isinstance(result, SwarmResult)
    assert result.mode == SwarmMode.SEQUENTIAL
    assert result.metadata["strategy"] == "chain"


@pytest.mark.asyncio
async def test_sequential_mode_chains_steps():
    """Sequential mode should pass through understand, plan, execute steps."""
    engine = SwarmEngine()
    provider = StubLLMProvider()
    result = await engine.execute_with_provider("summarize this text", provider)
    assert result.mode == SwarmMode.SEQUENTIAL
    assert result.metadata["steps"] == ["understand", "plan", "execute"]
    assert "stub response" in result.output


# ---------------------------------------------------------------------------
# Specialist mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_specialist_mode_returns_specialist_result():
    """Expert-level tasks should route to specialist mode."""
    engine = SwarmEngine()
    provider = StubLLMProvider()
    task = (
        "Research the latest machine learning papers, write a summary, "
        "and implement a code prototype using the data from the CSV dataset "
        "with a proper design architecture"
    )
    analysis = engine.analyze(task)
    assert analysis.suggested_mode == SwarmMode.SPECIALIST

    result = await engine.execute_with_provider(task, provider)
    assert isinstance(result, SwarmResult)
    assert result.mode == SwarmMode.SPECIALIST
    assert result.metadata["strategy"] == "expert-routing"


@pytest.mark.asyncio
async def test_specialist_mode_uses_domain_prompt():
    """Specialist mode should include detected domains in metadata."""
    engine = SwarmEngine()
    provider = StubLLMProvider()
    task = (
        "Research the latest machine learning papers, write a summary, "
        "and implement a code prototype using the data from the CSV dataset "
        "with a proper design architecture"
    )
    result = await engine.execute_with_provider(task, provider)
    assert "domains" in result.metadata
    assert len(result.metadata["domains"]) >= 3
    assert "stub response" in result.output


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


def test_existing_run_still_works():
    """Existing SwarmEngine.run() must keep working without a provider."""
    engine = SwarmEngine()
    result = engine.run("hi")
    assert result.mode == SwarmMode.SEQUENTIAL
    assert "hi" in result.output


def test_existing_analyze_still_works():
    """Existing SwarmEngine.analyze() must keep working."""
    engine = SwarmEngine()
    analysis = engine.analyze("hello world")
    assert analysis.complexity in TaskComplexity
    assert len(analysis.domains) >= 1


def test_engine_routes_to_specialist_still_works():
    """Existing specialist routing via run() must keep working."""
    engine = SwarmEngine()
    query = (
        "Research and analyze the data from multiple datasets, "
        "write a detailed code implementation with proper design, "
        "and calculate performance math metrics"
    )
    result = engine.run(query)
    assert result.mode == SwarmMode.SPECIALIST
    assert "specialist" in result.output


# ---------------------------------------------------------------------------
# v0.3.0 Phase 3: Red/Blue Executor (B3)
# ---------------------------------------------------------------------------


def test_red_blue_executor_sync():
    """Light mode: 10 templates, returns attack stats."""
    executor = RedBlueExecutor()
    result = executor.execute({})

    assert result.mode == SwarmMode.RED_BLUE
    assert result.metadata["attacks_blocked"] + result.metadata["attacks_passed"] == 10
    assert result.metadata["attacks_blocked"] > 0  # at least some blocked
    assert 0 <= result.metadata["coverage_score"] <= 100


@pytest.mark.asyncio
async def test_red_blue_async_with_provider():
    """Full mode with StubLLMProvider, generates attacks."""
    engine = SwarmEngine()
    provider = StubLLMProvider()
    # Call _run_red_blue directly since task analysis won't route here easily
    result = await engine._run_red_blue("test security of this system", provider)

    assert result.mode == SwarmMode.RED_BLUE
    assert "attacks_blocked" in result.metadata
    assert "attacks_passed" in result.metadata
    assert result.metadata["strategy"] == "adversarial-testing"


@pytest.mark.asyncio
async def test_red_blue_evidence_entries():
    """Results written to Evidence Pack."""
    engine = SwarmEngine()
    provider = StubLLMProvider()
    pack = EvidencePack(session_id="rb_evidence")

    await engine._run_red_blue(
        "test task", provider, evidence_pack=pack
    )

    # Evidence pack should have entries from the red/blue run
    assert len(pack.entries) > 0
    kinds = {e.kind for e in pack.entries}
    assert "tool_call" in kinds
    assert "decision" in kinds


def test_red_blue_coverage_score():
    """Coverage score between 0-100."""
    pipeline = GuardPipeline(guards=[RegexGuard()])
    executor = RedBlueExecutor(guard_pipeline=pipeline)
    result = executor.execute({})

    score = result.metadata["coverage_score"]
    assert 0.0 <= score <= 100.0
    # With the regex guard, it should block at least the instruction_override
    # and delimiter_injection templates
    assert result.metadata["attacks_blocked"] >= 2

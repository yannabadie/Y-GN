"""Tests for the RefinementHarness engine."""

import pytest

from ygn_brain.evidence import EvidencePack
from ygn_brain.harness.candidate import StubCandidateGenerator
from ygn_brain.harness.engine import RefinementHarness
from ygn_brain.harness.policy import DefaultPolicy
from ygn_brain.harness.selector import ConsensusSelector
from ygn_brain.harness.types import HarnessConfig
from ygn_brain.harness.verifier import TextVerifier


@pytest.mark.asyncio
async def test_engine_runs_and_produces_result():
    harness = RefinementHarness(
        generator=StubCandidateGenerator(
            output="Here is a detailed analysis of the problem with multiple points."
        ),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=2, min_score=0.5),
        selector=ConsensusSelector(),
    )
    config = HarnessConfig(
        providers=["stub"],
        candidates_per_provider=2,
        max_rounds=2,
        min_score=0.5,
    )
    result = await harness.run("analyze this", config)
    assert result.winner is not None
    assert result.winner.output != ""
    assert result.rounds_used >= 1


@pytest.mark.asyncio
async def test_engine_stops_when_score_reached():
    harness = RefinementHarness(
        generator=StubCandidateGenerator(
            output="A detailed and structured analysis:\n- Point 1\n- Point 2\n- Point 3"
        ),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=5, min_score=0.3),
        selector=ConsensusSelector(),
    )
    config = HarnessConfig(
        providers=["stub"],
        candidates_per_provider=1,
        max_rounds=5,
        min_score=0.3,
    )
    result = await harness.run("analyze", config)
    assert result.rounds_used == 1  # Stop after first round (score > 0.3)


@pytest.mark.asyncio
async def test_engine_traces_to_evidence():
    evidence = EvidencePack(session_id="harness-test")
    harness = RefinementHarness(
        generator=StubCandidateGenerator(output="A complete analysis with details and structure."),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=1, min_score=0.5),
        selector=ConsensusSelector(),
        evidence=evidence,
    )
    config = HarnessConfig(
        providers=["stub"],
        candidates_per_provider=1,
        max_rounds=1,
    )
    await harness.run("task", config)
    assert len(evidence.entries) > 0


@pytest.mark.asyncio
async def test_engine_multiple_rounds_on_low_score():
    """Engine should refine when the score does not meet the threshold."""
    harness = RefinementHarness(
        generator=StubCandidateGenerator(output="short"),
        verifier=TextVerifier(min_length=20),
        policy=DefaultPolicy(max_rounds=3, min_score=0.9),
        selector=ConsensusSelector(),
    )
    config = HarnessConfig(
        providers=["stub"],
        candidates_per_provider=1,
        max_rounds=3,
        min_score=0.9,
    )
    result = await harness.run("x", config)
    # With very short output the score will be low, so all 3 rounds should run
    assert result.rounds_used == 3
    assert result.total_candidates == 3


@pytest.mark.asyncio
async def test_engine_evidence_contains_decision_entry():
    """The final selection should be recorded as a 'decision' evidence entry."""
    evidence = EvidencePack(session_id="decision-test")
    harness = RefinementHarness(
        generator=StubCandidateGenerator(
            output="A detailed and structured analysis:\n- Point 1\n- Point 2"
        ),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=1, min_score=0.5),
        selector=ConsensusSelector(),
        evidence=evidence,
    )
    config = HarnessConfig(
        providers=["stub"],
        candidates_per_provider=1,
        max_rounds=1,
    )
    await harness.run("task", config)
    decision_entries = [e for e in evidence.entries if e.kind == "decision"]
    assert len(decision_entries) == 1
    assert decision_entries[0].data["action"] == "selection"


@pytest.mark.asyncio
async def test_engine_result_fields():
    """HarnessResult should have correct winner, feedback, counts."""
    harness = RefinementHarness(
        generator=StubCandidateGenerator(
            output="A detailed and structured analysis:\n- Point 1\n- Point 2"
        ),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=1, min_score=0.5),
        selector=ConsensusSelector(),
    )
    config = HarnessConfig(
        providers=["stub"],
        candidates_per_provider=2,
        max_rounds=1,
    )
    result = await harness.run("analyze", config)
    assert result.winner.provider == "stub"
    assert result.feedback.score > 0.0
    assert result.total_candidates == 2
    assert result.rounds_used == 1

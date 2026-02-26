"""E2E tests for Refinement Harness with real CLI providers.

Run: pytest tests/test_harness_e2e.py -v -m e2e
Skip if CLI not available.
"""

from __future__ import annotations

import shutil

import pytest

from ygn_brain.evidence import EvidencePack
from ygn_brain.harness.candidate import MultiProviderGenerator
from ygn_brain.harness.engine import RefinementHarness
from ygn_brain.harness.policy import DefaultPolicy
from ygn_brain.harness.selector import ConsensusSelector
from ygn_brain.harness.types import HarnessConfig
from ygn_brain.harness.verifier import TextVerifier


def _has_gemini_cli() -> bool:
    return shutil.which("gemini") is not None or shutil.which("gemini.cmd") is not None


def _has_codex_cli() -> bool:
    return shutil.which("codex") is not None or shutil.which("codex.cmd") is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_gemini_single():
    """Gemini CLI, single provider, 1 round."""
    if not _has_gemini_cli():
        pytest.skip("Gemini CLI not available")

    harness = RefinementHarness(
        generator=MultiProviderGenerator(),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=1, min_score=0.5),
        selector=ConsensusSelector(),
    )
    config = HarnessConfig(
        providers=["gemini"],
        candidates_per_provider=1,
        max_rounds=1,
    )
    result = await harness.run("Explain what a refinement loop is in 2 sentences.", config)
    assert result.winner.output != ""
    assert result.winner.provider == "gemini"
    assert result.feedback.score > 0.0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_ensemble():
    """Ensemble: Codex + Gemini."""
    if not _has_gemini_cli() or not _has_codex_cli():
        pytest.skip("Both Codex + Gemini CLI required")

    harness = RefinementHarness(
        generator=MultiProviderGenerator(),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=1, min_score=0.5),
        selector=ConsensusSelector(),
    )
    config = HarnessConfig(
        providers=["gemini", "codex"],
        candidates_per_provider=1,
        max_rounds=1,
        ensemble=True,
    )
    result = await harness.run("What is 2+2? Answer briefly.", config)
    assert result.winner.output != ""
    assert result.total_candidates >= 2


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_evidence_trace():
    """Evidence trace with real provider."""
    if not _has_gemini_cli():
        pytest.skip("Gemini CLI not available")

    evidence = EvidencePack(session_id="e2e-harness")
    harness = RefinementHarness(
        generator=MultiProviderGenerator(),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=1, min_score=0.5),
        selector=ConsensusSelector(),
        evidence=evidence,
    )
    config = HarnessConfig(providers=["gemini"], candidates_per_provider=1, max_rounds=1)
    await harness.run("Say hello", config)
    assert len(evidence.entries) > 0
    merkle = evidence.merkle_root_hash()
    assert len(merkle) > 0

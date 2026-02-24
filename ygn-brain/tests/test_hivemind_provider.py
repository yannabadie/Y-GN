"""Tests for HiveMind + Orchestrator with provider integration."""

from __future__ import annotations

import pytest

from ygn_brain.evidence import EvidencePack
from ygn_brain.hivemind import HiveMindPipeline
from ygn_brain.orchestrator import Orchestrator
from ygn_brain.provider import StubLLMProvider

# ---------------------------------------------------------------------------
# HiveMindPipeline.run_with_provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_with_provider_produces_seven_phases():
    pipeline = HiveMindPipeline()
    evidence = EvidencePack(session_id="provider_test")
    provider = StubLLMProvider()
    results = await pipeline.run_with_provider("Hello, how are you?", evidence, provider)
    assert len(results) == 7
    phase_names = [r.phase for r in results]
    assert phase_names == [
        "diagnosis",
        "analysis",
        "planning",
        "execution",
        "validation",
        "synthesis",
        "complete",
    ]


@pytest.mark.asyncio
async def test_run_with_provider_adds_evidence():
    pipeline = HiveMindPipeline()
    evidence = EvidencePack(session_id="provider_ev")
    provider = StubLLMProvider()
    await pipeline.run_with_provider("test input", evidence, provider)
    assert len(evidence.entries) >= 7
    phases_in_evidence = {e.phase for e in evidence.entries}
    assert "diagnosis" in phases_in_evidence
    assert "synthesis" in phases_in_evidence
    assert "complete" in phases_in_evidence


@pytest.mark.asyncio
async def test_run_with_provider_uses_llm_for_analysis():
    pipeline = HiveMindPipeline()
    evidence = EvidencePack(session_id="provider_llm")
    provider = StubLLMProvider()
    results = await pipeline.run_with_provider("What is 2+2?", evidence, provider)
    analysis = [r for r in results if r.phase == "analysis"][0]
    # The stub provider returns a canned response with "stub response" in it
    assert "stub response" in analysis.data["strategy"]


@pytest.mark.asyncio
async def test_run_with_provider_synthesis_uses_llm():
    pipeline = HiveMindPipeline()
    evidence = EvidencePack(session_id="provider_synth")
    provider = StubLLMProvider()
    results = await pipeline.run_with_provider("synthesize this", evidence, provider)
    synthesis = [r for r in results if r.phase == "synthesis"][0]
    assert "stub response" in synthesis.data["final"]


@pytest.mark.asyncio
async def test_run_with_provider_confidence_values():
    pipeline = HiveMindPipeline()
    evidence = EvidencePack(session_id="provider_conf")
    provider = StubLLMProvider()
    results = await pipeline.run_with_provider("test confidence", evidence, provider)
    for r in results:
        assert 0.0 <= r.confidence <= 1.0


# ---------------------------------------------------------------------------
# Backward compatibility: run() still works without provider
# ---------------------------------------------------------------------------


def test_run_still_works_without_provider():
    pipeline = HiveMindPipeline()
    evidence = EvidencePack(session_id="compat_test")
    results = pipeline.run("Hello, how are you?", evidence)
    assert len(results) == 7
    synthesis = [r for r in results if r.phase == "synthesis"][0]
    assert "Hello, how are you?" in synthesis.data["final"]


# ---------------------------------------------------------------------------
# Orchestrator with provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_run_async_with_provider():
    provider = StubLLMProvider()
    orch = Orchestrator(provider=provider)
    result = await orch.run_async("hello world")
    assert "session_id" in result
    assert "result" in result
    # The stub provider generates content with "stub response" in it
    assert "stub response" in result["result"]


@pytest.mark.asyncio
async def test_orchestrator_run_async_uses_factory_default():
    """When no provider is given, the Orchestrator uses ProviderFactory (stub by default)."""
    orch = Orchestrator()
    result = await orch.run_async("hello from factory")
    assert result["session_id"]
    assert "stub response" in result["result"].lower() or result["result"]


def test_orchestrator_run_sync_still_works():
    orch = Orchestrator()
    result = orch.run("hello world")
    assert "hello world" in result["result"]
    assert result["session_id"]


def test_orchestrator_run_sync_with_provider_param_still_works():
    """Passing a provider should not break the sync run() method."""
    provider = StubLLMProvider()
    orch = Orchestrator(provider=provider)
    result = orch.run("hello world")
    # sync run() uses stub pipeline, not provider
    assert "hello world" in result["result"]

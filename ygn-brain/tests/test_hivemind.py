"""Tests for hivemind module — 7-phase pipeline."""

from ygn_brain.evidence import EvidencePack
from ygn_brain.hivemind import HiveMindPipeline


def test_pipeline_produces_seven_phases():
    pipeline = HiveMindPipeline()
    evidence = EvidencePack(session_id="hm_test")
    results = pipeline.run("Hello, how are you?", evidence)
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


def test_pipeline_adds_evidence_entries():
    pipeline = HiveMindPipeline()
    evidence = EvidencePack(session_id="hm_ev")
    pipeline.run("test input", evidence)
    # Each phase should add at least one evidence entry
    assert len(evidence.entries) >= 7
    phases_in_evidence = {e.phase for e in evidence.entries}
    assert "diagnosis" in phases_in_evidence
    assert "synthesis" in phases_in_evidence
    assert "complete" in phases_in_evidence


def test_pipeline_synthesis_contains_input():
    pipeline = HiveMindPipeline()
    evidence = EvidencePack(session_id="hm_synth")
    results = pipeline.run("test the pipeline", evidence)
    synthesis = [r for r in results if r.phase == "synthesis"][0]
    assert "test the pipeline" in synthesis.data["final"]


def test_pipeline_confidence_values():
    pipeline = HiveMindPipeline()
    evidence = EvidencePack(session_id="hm_conf")
    results = pipeline.run("what is 2+2?", evidence)
    for r in results:
        assert 0.0 <= r.confidence <= 1.0

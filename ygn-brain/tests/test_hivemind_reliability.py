"""Tests for HiveMind reliability improvements."""

from ygn_brain.evidence import EvidencePack
from ygn_brain.hivemind import HiveMindPipeline, PhaseResult


def test_phase_result_dataclass():
    pr = PhaseResult(
        phase="diagnosis",
        status="ok",
        output="analyzed",
        latency_ms=42.0,
    )
    assert pr.phase == "diagnosis"
    assert pr.status == "ok"
    assert pr.output == "analyzed"
    assert pr.latency_ms == 42.0


def test_phase_result_all_statuses():
    for status in ("ok", "timeout", "error", "skipped"):
        pr = PhaseResult(phase="test", status=status, output="", latency_ms=0.0)
        assert pr.status == status


def test_phase_result_defaults():
    """PhaseResult new fields default gracefully for backward compatibility."""
    pr = PhaseResult(phase="diagnosis", data={"k": "v"}, confidence=0.9)
    assert pr.status == "ok"
    assert pr.output == ""
    assert pr.latency_ms == 0.0


def test_sync_run_completes():
    pipeline = HiveMindPipeline()
    evidence = EvidencePack(session_id="rel_test")
    results = pipeline.run("Test task", evidence)
    assert len(results) == 7
    assert len(evidence.entries) > 0
    # All phases should have a valid status
    for r in results:
        assert r.status in ("ok", "timeout", "error", "skipped")

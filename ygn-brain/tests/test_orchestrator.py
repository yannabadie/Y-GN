"""Tests for Orchestrator module."""

from ygn_brain.fsm import Phase
from ygn_brain.orchestrator import Orchestrator


def test_orchestrator_run():
    orch = Orchestrator()
    result = orch.run("hello world")
    assert "hello world" in result["result"]
    assert result["session_id"]


def test_orchestrator_completes_all_phases():
    orch = Orchestrator()
    orch.run("test")
    assert orch.state.phase == Phase.COMPLETE


def test_orchestrator_produces_evidence():
    orch = Orchestrator()
    orch.run("test input")
    assert len(orch.evidence.entries) > 0
    phases = {e.phase for e in orch.evidence.entries}
    assert "diagnosis" in phases
    assert "synthesis" in phases

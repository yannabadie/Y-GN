"""Lightweight orchestrator (Mediator pattern — replaces OrchestratorV7 god-object)."""

from __future__ import annotations

import uuid
from typing import Any

from .evidence import EvidencePack
from .fsm import FSMState, Phase


class Orchestrator:
    """Minimal orchestrator that drives the HiveMind 7-phase pipeline."""

    def __init__(self) -> None:
        self.state = FSMState()
        self.evidence = EvidencePack(session_id=uuid.uuid4().hex[:12])

    def run(self, user_input: str) -> dict[str, Any]:
        """Execute a full pipeline pass (stub implementation for M0/M2)."""
        # Phase 1: Diagnosis
        self.state = self.state.transition(Phase.DIAGNOSIS)
        self.evidence.add("diagnosis", "input", {"user_input": user_input})

        # Phase 2: Analysis
        self.state = self.state.transition(Phase.ANALYSIS)
        self.evidence.add("analysis", "decision", {"strategy": "direct"})

        # Phase 3: Planning
        self.state = self.state.transition(Phase.PLANNING)
        plan = {"steps": [{"action": "respond", "content": f"Processed: {user_input}"}]}
        self.evidence.add("planning", "decision", {"plan": plan})

        # Phase 4: Execution
        self.state = self.state.transition(Phase.EXECUTION)
        result = plan["steps"][0]["content"]
        self.evidence.add("execution", "output", {"result": result})

        # Phase 5: Validation
        self.state = self.state.transition(Phase.VALIDATION)
        self.evidence.add("validation", "decision", {"passed": True})

        # Phase 6: Synthesis
        self.state = self.state.transition(Phase.SYNTHESIS)
        self.evidence.add("synthesis", "output", {"final": result})

        # Phase 7: Complete
        self.state = self.state.transition(Phase.COMPLETE)

        return {"result": result, "session_id": self.evidence.session_id}

"""Finite State Machine for orchestration phases."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class Phase(StrEnum):
    IDLE = "idle"
    DIAGNOSIS = "diagnosis"
    ANALYSIS = "analysis"
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"


# Valid phase transitions (HiveMind 7-phase pipeline)
_TRANSITIONS: dict[Phase, list[Phase]] = {
    Phase.IDLE: [Phase.DIAGNOSIS],
    Phase.DIAGNOSIS: [Phase.ANALYSIS],
    Phase.ANALYSIS: [Phase.PLANNING],
    Phase.PLANNING: [Phase.EXECUTION],
    Phase.EXECUTION: [Phase.VALIDATION],
    Phase.VALIDATION: [Phase.SYNTHESIS, Phase.EXECUTION],  # can retry
    Phase.SYNTHESIS: [Phase.COMPLETE],
    Phase.COMPLETE: [Phase.IDLE],
}


class FSMState(BaseModel):
    phase: Phase = Phase.IDLE
    context: dict[str, Any] = {}

    def can_transition(self, target: Phase) -> bool:
        return target in _TRANSITIONS.get(self.phase, [])

    def transition(self, target: Phase) -> FSMState:
        if not self.can_transition(target):
            raise ValueError(f"Invalid transition: {self.phase} -> {target}")
        return FSMState(phase=target, context=self.context)

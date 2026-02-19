"""Y-GN Brain — cognitive control-plane."""

from __future__ import annotations

__version__ = "0.1.0"

from .context import ContextBuilder, ExecutionContext
from .evidence import EvidenceEntry, EvidencePack
from .fsm import FSMState, Phase
from .guard import GuardPipeline, GuardResult, InputGuard, ThreatLevel
from .hivemind import HiveMindPipeline, PhaseResult
from .memory import InMemoryBackend, MemoryCategory, MemoryEntry, MemoryService
from .orchestrator import Orchestrator
from .swarm import (
    ParallelExecutor,
    SequentialExecutor,
    SpecialistExecutor,
    SwarmEngine,
    SwarmExecutor,
    SwarmMode,
    SwarmResult,
    TaskAnalysis,
    TaskAnalyzer,
    TaskComplexity,
)

__all__ = [
    "ContextBuilder",
    "ExecutionContext",
    "EvidenceEntry",
    "EvidencePack",
    "FSMState",
    "GuardPipeline",
    "GuardResult",
    "HiveMindPipeline",
    "InMemoryBackend",
    "InputGuard",
    "MemoryCategory",
    "MemoryEntry",
    "MemoryService",
    "Orchestrator",
    "ParallelExecutor",
    "Phase",
    "PhaseResult",
    "SequentialExecutor",
    "SpecialistExecutor",
    "SwarmEngine",
    "SwarmExecutor",
    "SwarmMode",
    "SwarmResult",
    "TaskAnalysis",
    "TaskAnalyzer",
    "TaskComplexity",
    "ThreatLevel",
]

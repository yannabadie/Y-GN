"""Y-GN Brain — cognitive control-plane."""

from __future__ import annotations

__version__ = "0.1.0"

from .context import ContextBuilder, ExecutionContext
from .evidence import EvidenceEntry, EvidencePack
from .fsm import FSMState, Phase
from .guard import GuardPipeline, GuardResult, InputGuard, ThreatLevel
from .hivemind import HiveMindPipeline, PhaseResult
from .mcp_client import McpClient, McpError
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
from .tool_bridge import McpToolBridge

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
    "McpClient",
    "McpError",
    "McpToolBridge",
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

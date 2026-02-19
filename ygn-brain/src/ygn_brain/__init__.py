"""Y-GN Brain — cognitive control-plane."""

from __future__ import annotations

__version__ = "0.1.0"

from .context import ContextBuilder, ExecutionContext
from .context_compression import CompressedContext, CompressionStrategy, ContextCompressor
from .dylan_metrics import AgentMetrics, DyLANTracker
from .event_sourcing import EventStore, FSMEvent, InMemoryEventStore
from .evidence import EvidenceEntry, EvidencePack
from .evolution import (
    EvolutionEngine,
    EvolutionProposal,
    EvolutionResult,
    EvolutionScope,
    FileWhitelist,
    GateCheckResult,
    SafetyGuard,
)
from .fsm import FSMState, Phase
from .guard import GuardPipeline, GuardResult, InputGuard, ThreatLevel
from .hivemind import HiveMindPipeline, PhaseResult
from .mcp_client import McpClient, McpError
from .memory import InMemoryBackend, MemoryCategory, MemoryEntry, MemoryService
from .orchestrator import Orchestrator
from .success_memory import SuccessMemory, SuccessRecord
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
from .teaming import (
    AgentProfile,
    DistributedSwarmEngine,
    FlowController,
    FlowPolicy,
    TeamBuilder,
    TeamFormation,
)
from .telemetry import (
    TelemetryConfig,
    YgnTracer,
    trace_guard_check,
    trace_hivemind_phase,
    trace_mcp_call,
    trace_orchestrator_run,
)
from .tiered_memory import (
    ColdEntry,
    HotEntry,
    MemoryTier,
    TieredMemoryService,
    WarmEntry,
)
from .tool_bridge import McpToolBridge
from .uacp import UacpCodec, UacpMessage, UacpVerb
from .vla_adapter import (
    StubVLAAdapter,
    VLAAdapter,
    VLABridge,
    VLAInput,
    VLAOutput,
)

__all__ = [
    "AgentMetrics",
    "AgentProfile",
    "CompressedContext",
    "CompressionStrategy",
    "ContextBuilder",
    "ContextCompressor",
    "DistributedSwarmEngine",
    "DyLANTracker",
    "EventStore",
    "EvolutionEngine",
    "EvolutionProposal",
    "EvolutionResult",
    "EvolutionScope",
    "ExecutionContext",
    "EvidenceEntry",
    "EvidencePack",
    "FSMEvent",
    "FSMState",
    "FileWhitelist",
    "FlowController",
    "FlowPolicy",
    "GateCheckResult",
    "GuardPipeline",
    "GuardResult",
    "HiveMindPipeline",
    "InMemoryBackend",
    "InMemoryEventStore",
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
    "StubVLAAdapter",
    "SwarmEngine",
    "SwarmExecutor",
    "SwarmMode",
    "SafetyGuard",
    "SuccessMemory",
    "SuccessRecord",
    "SwarmResult",
    "TaskAnalysis",
    "TaskAnalyzer",
    "TaskComplexity",
    "TeamBuilder",
    "TeamFormation",
    "TelemetryConfig",
    "ThreatLevel",
    "YgnTracer",
    "VLAAdapter",
    "VLABridge",
    "VLAInput",
    "VLAOutput",
    "UacpCodec",
    "UacpMessage",
    "UacpVerb",
    "trace_guard_check",
    "trace_hivemind_phase",
    "trace_mcp_call",
    "trace_orchestrator_run",
    "ColdEntry",
    "HotEntry",
    "MemoryTier",
    "TieredMemoryService",
    "WarmEntry",
]

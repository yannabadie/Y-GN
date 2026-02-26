"""Y-GN Brain — cognitive control-plane."""

from __future__ import annotations

__version__ = "0.3.0"

from .codex_provider import CodexCliError, CodexCliProvider
from .context import ContextBuilder, ExecutionContext
from .context_compression import CompressedContext, CompressionStrategy, ContextCompressor
from .conversation import ConversationMemory, ConversationTurn
from .cosine import cosine_similarity
from .dylan_metrics import AgentMetrics, DyLANTracker
from .embeddings import (
    EmbeddingService,
    LocalEmbeddingService,
    OllamaEmbeddingService,
    StubEmbeddingService,
)
from .event_sourcing import EventStore, FSMEvent, InMemoryEventStore
from .evidence import EvidenceEntry, EvidenceKind, EvidencePack
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
from .gemini_provider import GeminiCliError, GeminiCliProvider
from .guard import (
    GuardBackend,
    GuardPipeline,
    GuardResult,
    InputGuard,
    RegexGuard,
    ThreatLevel,
    ToolInvocationGuard,
)
from .guard_backends import ClassifierGuard, StubClassifierGuard
from .hivemind import HiveMindPipeline, PhaseResult
from .mcp_client import McpClient, McpError
from .memory import InMemoryBackend, MemoryCategory, MemoryEntry, MemoryService
from .orchestrator import Orchestrator
from .personality import AgentPersonality, PersonalityRegistry, PersonalityTrait
from .provider import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    LLMProvider,
    ProviderCapabilities,
    StubLLMProvider,
    TokenUsage,
    ToolCall,
    ToolSpec,
)
from .provider_factory import ProviderFactory
from .provider_router import ModelSelector, ProviderRouter
from .success_memory import SuccessMemory, SuccessRecord
from .swarm import (
    ParallelExecutor,
    RedBlueExecutor,
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
    "CodexCliError",
    "CodexCliProvider",
    "AgentPersonality",
    "AgentProfile",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ChatRole",
    "ColdEntry",
    "CompressedContext",
    "CompressionStrategy",
    "ContextBuilder",
    "ContextCompressor",
    "ConversationMemory",
    "ConversationTurn",
    "cosine_similarity",
    "DistributedSwarmEngine",
    "DyLANTracker",
    "EmbeddingService",
    "EventStore",
    "EvolutionEngine",
    "EvolutionProposal",
    "EvolutionResult",
    "EvolutionScope",
    "ExecutionContext",
    "EvidenceEntry",
    "EvidenceKind",
    "EvidencePack",
    "FSMEvent",
    "FSMState",
    "FileWhitelist",
    "FlowController",
    "FlowPolicy",
    "GateCheckResult",
    "GeminiCliError",
    "GeminiCliProvider",
    "GuardBackend",
    "GuardPipeline",
    "GuardResult",
    "HiveMindPipeline",
    "HotEntry",
    "InMemoryBackend",
    "InMemoryEventStore",
    "InputGuard",
    "ClassifierGuard",
    "StubClassifierGuard",
    "RegexGuard",
    "ToolInvocationGuard",
    "LocalEmbeddingService",
    "LLMProvider",
    "McpClient",
    "McpError",
    "McpToolBridge",
    "MemoryCategory",
    "MemoryEntry",
    "MemoryService",
    "MemoryTier",
    "ModelSelector",
    "OllamaEmbeddingService",
    "Orchestrator",
    "ParallelExecutor",
    "RedBlueExecutor",
    "PersonalityRegistry",
    "PersonalityTrait",
    "Phase",
    "PhaseResult",
    "ProviderCapabilities",
    "ProviderFactory",
    "ProviderRouter",
    "SafetyGuard",
    "SequentialExecutor",
    "SpecialistExecutor",
    "StubEmbeddingService",
    "StubLLMProvider",
    "StubVLAAdapter",
    "SuccessMemory",
    "SuccessRecord",
    "SwarmEngine",
    "SwarmExecutor",
    "SwarmMode",
    "SwarmResult",
    "TaskAnalysis",
    "TaskAnalyzer",
    "TaskComplexity",
    "TeamBuilder",
    "TeamFormation",
    "TelemetryConfig",
    "ThreatLevel",
    "TieredMemoryService",
    "TokenUsage",
    "ToolCall",
    "ToolSpec",
    "UacpCodec",
    "UacpMessage",
    "UacpVerb",
    "VLAAdapter",
    "VLABridge",
    "VLAInput",
    "VLAOutput",
    "WarmEntry",
    "YgnTracer",
    "trace_guard_check",
    "trace_hivemind_phase",
    "trace_mcp_call",
    "trace_orchestrator_run",
]

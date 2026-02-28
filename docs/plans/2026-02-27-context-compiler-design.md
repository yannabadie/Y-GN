# Context Compiler & Tool Interrupts — Design Document

**Date**: 2026-02-27
**Version target**: v0.8.0
**Status**: Approved

## Problem Statement

Y-GN v0.7.0 builds LLM context once via `ContextBuilder.build()` and passes it through
the HiveMind pipeline without budget control. Tool outputs enter the prompt verbatim,
regardless of size. There is no typed event system for tool interactions, and no
normalization of tool outputs before they reach the LLM.

This causes:
- **Token waste**: Large tool outputs (file contents, command results) consume context
  budget without proportional value.
- **Lost-in-the-middle**: LLMs lose track of relevant information buried in long contexts.
- **No budget enforcement**: Context can grow unbounded, causing truncation or API errors.
- **Untyped tool interactions**: No structured handling of success/error/timeout events.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Token budget | Configurable, no default | Forces conscious choice at deployment |
| ArtifactStore backend | SQLite + FS fallback | SQLite primary (consistent with guard_log), FS for simplicity |
| Session vs EvidencePack | Session wraps EvidencePack | Non-breaking; existing Evidence tests pass unchanged |
| Schema validation | JSON Schema per tool | Strict validation; each tool declares output schema |
| Architecture | Layered subpackages | Follows repo pattern (like harness/); clean separation |

## Architecture

### New Subpackages

```
ygn-brain/src/ygn_brain/
├── context_compiler/          # NEW
│   ├── __init__.py
│   ├── session.py             # Session(EventLog) wrapping EvidencePack
│   ├── working_context.py     # WorkingContext (compiled view for LLM)
│   ├── processors.py          # Named processor pipeline
│   ├── artifact_store.py      # ArtifactStore ABC + SQLite + FS backends
│   └── token_budget.py        # Budget tracker
├── tool_interrupt/            # NEW
│   ├── __init__.py
│   ├── events.py              # ToolEvent, ToolEventKind
│   ├── handler.py             # ToolInterruptHandler
│   ├── normalizer.py          # PerceptionAligner
│   └── schemas.py             # SchemaRegistry
```

### Data Flow

```
User Input
    ↓
Session.record("user_input", data, tokens)
    ↓
ContextCompiler.compile(session, budget)
    ├── HistorySelector:   keep first + last N turns, drop middle
    ├── Compactor:         merge consecutive same-role, trim, truncate
    ├── MemoryPreloader:   query memory service, inject top-K
    └── ArtifactAttacher:  replace large payloads with {handle, summary}
    ↓
WorkingContext (within budget)
    ↓
HiveMindPipeline.run_from_context(working_ctx, evidence)
    ↓
Tool calls via ToolInterruptHandler
    ├── Emit CALL event → Session
    ├── Execute via McpToolBridge (with timeout)
    ├── Normalize via PerceptionAligner (schema + redact + summarize)
    ├── Externalize large results → ArtifactStore
    └── Emit SUCCESS/ERROR/TIMEOUT event → Session
    ↓
Result
```

## Component Details

### 1. Session & EventLog (`context_compiler/session.py`)

```python
@dataclass
class SessionEvent:
    event_id: str          # time-sortable
    timestamp: float
    kind: str              # "user_input", "memory_hit", "tool_call", "tool_success",
                           #  "tool_error", "guard_decision", "phase_result", "artifact_stored"
    data: dict[str, Any]
    token_estimate: int    # words * 1.3 (no tokenizer dep)

class EventLog:
    events: list[SessionEvent]
    def append(kind, data, token_estimate) -> SessionEvent
    def filter(kinds) -> list[SessionEvent]
    def total_tokens() -> int
    def since(timestamp) -> list[SessionEvent]

class Session:
    session_id: str
    event_log: EventLog
    evidence: EvidencePack
    def record(kind, data, token_estimate) -> SessionEvent
    def to_evidence_pack() -> EvidencePack
```

### 2. WorkingContext (`context_compiler/working_context.py`)

```python
@dataclass
class WorkingContext:
    system_prompt: str
    history: list[dict]
    memory_hits: list[dict]
    artifact_refs: list[dict]    # {handle, summary, size_bytes}
    tool_results: list[dict]
    token_count: int
    budget: int

    def is_within_budget() -> bool
    def overflow() -> int
    def to_messages() -> list[dict]  # format for provider.chat()
```

### 3. Processor Pipeline (`context_compiler/processors.py`)

Processors follow a `Protocol`:
```python
class Processor(Protocol):
    name: str
    def process(session, ctx, budget) -> WorkingContext
```

Built-in processors:
- **HistorySelector**: Keep first + last N events, drop middle if over budget.
- **Compactor**: Merge consecutive same-role messages, trim whitespace.
- **MemoryPreloader**: Query MemoryService, inject top-K relevant memories.
- **ArtifactAttacher**: Replace payloads > threshold with artifact handles + summaries.

**ContextCompiler** runs processors in order, checking budget after each.

### 4. ArtifactStore (`context_compiler/artifact_store.py`)

```python
@dataclass
class ArtifactHandle:
    artifact_id: str       # SHA-256 of content
    summary: str           # first ~200 chars
    size_bytes: int
    mime_type: str
    created_at: float
    source: str            # e.g. "tool:echo"

class ArtifactStore(ABC):
    def store(content, source, mime_type) -> ArtifactHandle
    def retrieve(artifact_id) -> bytes | None
    def exists(artifact_id) -> bool
    def list_handles(session_id) -> list[ArtifactHandle]
    def delete(artifact_id) -> bool

class SqliteArtifactStore(ArtifactStore): ...  # BLOBs, content-addressed
class FsArtifactStore(ArtifactStore): ...      # files with 2-char prefix dirs
```

### 5. Tool Interrupts (`tool_interrupt/`)

```python
class ToolEventKind(StrEnum):
    CALL = "tool_call"
    SUCCESS = "tool_success"
    ERROR = "tool_error"
    TIMEOUT = "tool_timeout"

class ToolInterruptHandler:
    # Wraps McpToolBridge + Session + ArtifactStore
    async def call(tool_name, arguments, timeout_sec) -> ToolEvent

class PerceptionAligner:
    # Schema validation + secret redaction + summarization
    def normalize(tool_name, raw_output) -> dict

class SchemaRegistry:
    # Per-tool JSON Schema registry
    def register(tool_name, schema)
    def validate(tool_name, data) -> (valid, errors)
```

## Integration with Existing Code

1. **orchestrator.py**: New `run_compiled(user_input, budget)` method (~30 lines).
   Existing `run()` and `run_async()` unchanged.

2. **hivemind.py**: New `run_from_context(working_ctx, evidence, provider)` (~15 lines).
   Accepts WorkingContext instead of raw string.

3. **mcp_server.py**: New `orchestrate_compiled` tool (~20 lines).
   Uses `run_compiled()` path, returns artifact handles.

## Testing Plan

| Test file | Count | Coverage |
|-----------|-------|----------|
| test_session.py | 3 | EventLog append/filter/total_tokens, Session wraps EvidencePack |
| test_working_context.py | 2 | Budget checking, to_messages() formatting |
| test_processors.py | 4 | Each processor in isolation |
| test_artifact_store.py | 3 | SQLite + FS store/retrieve/dedup, handle generation |
| test_tool_interrupt.py | 3 | Success/error/timeout events, normalization, externalization |
| test_context_compiler_e2e.py | 2 | Full pipeline: large payload externalized, budget respected |

Total: ~17 new tests.

## Demo

CLI entry point `ygn-brain-demo-compiler`:
1. Creates a session with user input
2. Simulates a large tool output (10KB text)
3. Runs context compiler with budget
4. Prints WorkingContext showing artifact handle (not full payload)
5. Shows artifact retrievable by handle

## Constraints

- No new API costs (all tests use StubLLMProvider)
- No new external dependencies (jsonschema is optional)
- Existing tests unchanged (backward compatible)
- `make test` must pass (Python + Rust)

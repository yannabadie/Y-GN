# Fact Pack

Collected facts, assumptions, and open questions for Y-GN (Yggdrasil-Grid Nexus).
Generated 2026-02-19.

---

## Confirmed

Facts verified against the Y-GN codebase. Each item references the source file(s).

1. **Brain-Core integration uses MCP (JSON-RPC 2.0 over stdio).** The Rust side implements a JSON-RPC 2.0 server that exposes the tool registry; the Python side spawns `ygn-core mcp` as a subprocess and exchanges newline-delimited messages.
   — `ygn-core/src/mcp.rs`, `ygn-brain/src/ygn_brain/mcp_client.py`

2. **Orchestrator is a lightweight Mediator (not an OrchestratorV7 god-object).** It composes Guard, Memory, Context, and HiveMind as collaborators and delegates all work to them.
   — `ygn-brain/src/ygn_brain/orchestrator.py`

3. **HiveMind runs 7 phases: Diagnosis, Analysis, Planning, Execution, Validation, Synthesis, Complete.** The FSM enforces valid transitions (Validation may loop back to Execution for retries).
   — `ygn-brain/src/ygn_brain/hivemind.py`, `ygn-brain/src/ygn_brain/fsm.py`

4. **SwarmEngine supports 6 modes: Parallel, Sequential, RedBlue, PingPong, LeadSupport, Specialist.** A `TaskAnalyzer` selects the mode based on complexity and domain analysis.
   — `ygn-brain/src/ygn_brain/swarm.py`

5. **Memory is 3-tier: Hot (TTL-based cache), Warm (tag-indexed), Cold (relation-linked persistent).** Promotion and eviction flow between tiers automatically.
   — `ygn-brain/src/ygn_brain/tiered_memory.py`

6. **SQLite FTS5 with BM25 ranking for Core memory.** `SqliteMemory` stores entries with full-text search, WAL mode, and category-based filtering.
   — `ygn-core/src/sqlite_memory.rs`

7. **ProcessSandbox with 4 profiles: NoNet, Net, ReadOnlyFs, ScratchFs.** Each profile defines allowed/denied `AccessKind` values (Network, FileRead, FileWrite, Command). Access checks produce an `AccessResult` with allow/deny and reason.
   — `ygn-core/src/sandbox.rs`

8. **PolicyEngine with Allow / Deny / RequireApproval decisions.** Evaluates tool-call requests against security rules, sandbox restrictions, and explicit allow/deny lists. Includes risk classification (Low/Medium/High/Critical).
   — `ygn-core/src/policy.rs`

9. **uACP codec with identical wire format in Rust and Python.** Big-endian binary framing: `[1B verb][4B msg_id][8B timestamp][2B sender_len][sender][4B payload_len][payload]`. Supports four verbs: PING, TELL, ASK, OBSERVE.
   — `ygn-core/src/uacp.rs`, `ygn-brain/src/ygn_brain/uacp.py`

10. **Node registry with discovery filters.** `InMemoryRegistry` stores `NodeInfo` (role, trust tier, endpoint, capabilities) and supports filtered discovery by role, trust, and capabilities.
    — `ygn-core/src/registry.rs`

11. **Guard pipeline detects 3 prompt-injection categories: Instruction Override, Role Manipulation, and Data Extraction.** Uses compiled regex patterns per category and returns a `GuardResult` with threat level (None/Low/Medium/High/Critical).
    — `ygn-brain/src/ygn_brain/guard.py`

12. **DiagnosticEngine classifies 7 error categories: DependencyMissing, CompilationError, TestFailure, LintViolation, ConfigurationError, RuntimePanic, Unknown.** Parses gate output via regex to produce diagnostics with proposed fixes.
    — `ygn-core/src/diagnostics.rs`

13. **EvolutionEngine with file whitelist and safety guard.** Proposes scaffold modifications (config, test, tooling, documentation scopes), validates against a `FileWhitelist`, generates unified diffs, and runs quality gates before applying.
    — `ygn-brain/src/ygn_brain/evolution.py`

14. **Hardware simulator (Drive/Sense/Look/Speak) exposed as MCP tool.** `SimulatedHardware` tracks position/heading in-memory; `HardwareTool` wraps it as an MCP-compatible `Tool` for embodiment experiments.
    — `ygn-core/src/hardware.rs`

15. **EvidencePack produces auditable execution traces.** Each pipeline run generates a `session_id`-stamped JSONL file with timestamped entries (phase, kind, data) for every decision point.
    — `ygn-brain/src/ygn_brain/evidence.py`

16. **Audit trail records security-relevant events.** Events include ToolCallAttempt, AccessDenied, AccessGranted, ApprovalRequired, and PolicyViolation with full metadata.
    — `ygn-core/src/audit.rs`

17. **ContextBuilder assembles execution context from services.** Combines user input, guard result, memory recall, and evidence pack into an `ExecutionContext` that the orchestrator passes to HiveMind.
    — `ygn-brain/src/ygn_brain/context.py`

18. **McpToolBridge provides discover-then-execute workflow.** Wraps `McpClient` so the orchestrator can discover and invoke Core tools without knowing MCP protocol details.
    — `ygn-brain/src/ygn_brain/tool_bridge.py`

19. **Dynamic Teaming with AgentProfile, TeamFormation, and FlowPolicy.** Builds teams from distributed agent profiles, assigns lead agents, and selects swarm strategies based on task analysis.
    — `ygn-brain/src/ygn_brain/teaming.py`

20. **VLA (Vision-Language-Action) adapter for embodiment.** Abstract `VLAAdapter` interface maps image+instruction inputs to hardware action sequences with confidence scores.
    — `ygn-brain/src/ygn_brain/vla_adapter.py`

21. **Observer trait for pluggable observability backends.** Supports events for AgentStart, LlmRequest, LlmResponse, ToolCallStart, ToolCall, and more with timestamps for OpenTelemetry-compatible tracing.
    — `ygn-core/src/observer.rs`

22. **Channel trait for message adapters (CLI, Telegram, Discord).** Defines `ChannelMessage` (inbound) and `SendMessage` (outbound) with channel name, sender, and metadata fields.
    — `ygn-core/src/channel.rs`

23. **Echo tool parameter is `input`, not `text`.** The `EchoTool` in `ygn-core/src/tool.rs` defines its JSON Schema with `{"input": {"type": "string"}}` and `required: ["input"]`. Prior docs/examples/tests incorrectly used `{"text": "..."}`. Fixed in v0.1.0.
    — `ygn-core/src/tool.rs:78-86`, `examples/03_mcp_integration.py`, `INSTALL.md`

24. **REPL async_main() always uses StubLLMProvider regardless of API keys.** The function detects `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` but has no real provider implementations in Python. Messages now accurately reflect this.
    — `ygn-brain/src/ygn_brain/repl.py`

25. **Mock MCP server in tests must mirror real ygn-core tool schemas.** A regression test (`test_echo_tool_schema_has_input_parameter`) now validates that the mock echo tool uses `input` (not `text`) matching the real `EchoTool`.
    — `ygn-brain/tests/test_mcp_client.py`

26. **MCP tools/call panics when main uses #[tokio::main].** The `handle_tools_call` method created a new `tokio::runtime::Runtime` inside a synchronous function called from `#[tokio::main]`, causing "Cannot start a runtime from within a runtime" panic. Fixed by using `Handle::try_current()` + `block_in_place` when an existing runtime is detected.
    — `ygn-core/src/mcp.rs:284-291`

---

## Assumptions

From ROADMAP and design intent; to be validated further.

1. **WASM/WASI runtime will use wasmtime.** Currently using `ProcessSandbox` with profile-based access control; no wasmtime/wasmer integration exists yet.

2. **A2A protocol may be needed for agent-to-agent communication.** Not implemented; uACP covers the current edge-constrained multi-agent case with PING/TELL/ASK/OBSERVE verbs.

3. **HippoRAG (KG + Personalized PageRank) for multi-hop retrieval.** The cold tier has relation links but no PageRank or graph traversal algorithm yet.

4. **Temporal Knowledge Graph (Zep/Graphiti-inspired).** Cold tier stores relations with timestamps but lacks a full graph store or temporal query engine.

5. **OS sandboxing (landlock/bwrap) for deeper isolation.** Not implemented; the current sandbox is a logical `ProcessSandbox` with profile-based checks, not kernel-level enforcement.

6. **HeteroGAT-Rank for supply-chain behavior analysis.** Not implemented; no GNN or graph attention network code exists in the codebase.

7. **Telegram channel integration for edge node.** The `Channel` trait exists in `ygn-core/src/channel.rs` but no real channel adapters (Telegram, Discord, etc.) are implemented yet.

---

## Open Questions / TODO

1. Should the WASM runtime be wasmtime or wasmer? Trade-offs around WASI compliance, component model support, and compile speed need evaluation.

2. When to add real LLM provider integration (beyond StubProvider)? The `Provider` trait is defined but only stubs exist. Anthropic/OpenAI/Ollama adapters are needed for real execution.

3. Redis/Postgres backend for distributed registry? `InMemoryRegistry` works for single-node; multi-node deployments need a shared store.

4. Real channel adapters (Telegram, Discord) -- what is the priority order? The `Channel` trait is ready but no concrete adapters ship.

5. Evidence Pack schema formalization (JSON Schema validation)? Currently free-form `dict[str, Any]`; a strict schema would improve auditability and interop.

6. Should the cold memory tier evolve into a full graph database (e.g., Neo4j, Memgraph) or stay as an embedded relational model with relation links?

7. What is the graduation criteria for moving ProcessSandbox to OS-level sandboxing (landlock on Linux, sandbox-exec on macOS)?

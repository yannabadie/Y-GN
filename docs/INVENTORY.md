# Y-GN Inventory

Generated 2026-02-19. Reflects the codebase after milestones M0-M8.

---

## Languages

- **Rust** (`ygn-core`): systems data-plane -- tool execution, sandboxing, memory, MCP server, registry, diagnostics
- **Python** (`ygn-brain`): cognitive control-plane -- orchestration, multi-agent swarm, HiveMind pipeline, guard, evidence

## Entrypoints

- `ygn-core/src/main.rs` -- CLI binary with subcommands: `status`, `gateway`, `config`, `tools`, `providers`, `mcp`, `registry`, `diagnose`
- `ygn-brain/src/ygn_brain/repl.py` -- Interactive Python REPL (`ygn-brain-repl` script entry)
- `ygn-brain/src/ygn_brain/orchestrator.py` -- Orchestrator API (programmatic entry for pipeline runs)

## Crates / Packages

| Name | Language | Manifest | Description |
|------|----------|----------|-------------|
| `ygn-core` | Rust | `ygn-core/Cargo.toml` | Data-plane: tool execution, channels, tunnels, sandboxing, memory |
| `ygn-brain` | Python | `ygn-brain/pyproject.toml` | Cognitive control-plane: orchestration, multi-agent swarm, evidence packs |

---

## Module Map

### ygn-core (Rust)

Source files under `ygn-core/src/`:

| File | Description |
|------|-------------|
| `main.rs` | CLI binary entry point (clap-based subcommands: status, gateway, config, tools, providers, mcp, registry, diagnose) |
| `lib.rs` | Crate root -- re-exports all public modules |
| `config.rs` | Node configuration (role, trust tier, gateway bind) with JSON Schema export |
| `gateway.rs` | Axum HTTP gateway with `/health` endpoint |
| `provider.rs` | LLM Provider trait and types (ChatRequest/ChatResponse, ProviderCapabilities) |
| `tool.rs` | Tool trait, ToolSpec metadata, ToolRegistry, and built-in EchoTool |
| `observer.rs` | Observability trait and event types (AgentStart, LlmRequest, ToolCall, etc.) |
| `channel.rs` | Channel trait for message adapters (ChannelMessage, SendMessage) |
| `memory.rs` | Memory trait and types (MemoryEntry, MemoryCategory: Core/Daily/Conversation/Custom) |
| `security.rs` | Security policy types (AutonomyLevel: Ask/Allow/Deny, SecurityPolicy with path/command allowlists) |
| `policy.rs` | Unified PolicyEngine -- evaluates tool-call requests and produces Allow/Deny/RequireApproval decisions with risk levels |
| `audit.rs` | Security audit trail (AuditEntry, AuditLog) recording tool-call attempts, access decisions, and policy violations |
| `sandbox.rs` | Process-based sandbox engine with 4 profiles (NoNet, Net, ReadOnlyFs, ScratchFs) and access checking |
| `sqlite_memory.rs` | SQLite-backed memory store with FTS5 full-text search and BM25 ranking |
| `mcp.rs` | MCP server (JSON-RPC 2.0 over stdio) exposing the tool registry to ygn-brain |
| `hardware.rs` | Simulated hardware backend (Drive/Sense/Look/Speak) with HardwareTool MCP wrapper |
| `registry.rs` | Node registry and discovery system (NodeInfo, InMemoryRegistry, DiscoveryFilter) |
| `uacp.rs` | Micro Agent Communication Protocol codec -- binary framing with 4 verbs (PING/TELL/ASK/OBSERVE) |
| `diagnostics.rs` | Auto-diagnostic engine -- classifies 7 error categories and proposes fixes for quality gate failures |

Integration tests:

| File | Description |
|------|-------------|
| `tests/smoke_test.rs` | End-to-end smoke tests exercising public APIs across module boundaries (3 tests) |

### ygn-brain (Python)

Source files under `ygn-brain/src/ygn_brain/`:

| File | Description |
|------|-------------|
| `__init__.py` | Package root -- re-exports all public classes and types |
| `orchestrator.py` | Lightweight Mediator orchestrator driving the HiveMind pipeline with guard and memory |
| `hivemind.py` | HiveMind 7-phase cognitive pipeline (Diagnosis through Complete) with evidence generation |
| `fsm.py` | Finite State Machine for orchestration phases with enforced valid transitions |
| `swarm.py` | Hybrid Swarm Engine with 6 execution modes and task complexity analysis |
| `guard.py` | Security guard pipeline detecting 3 prompt-injection categories (Instruction Override, Role Manipulation, Data Extraction) |
| `memory.py` | Memory service abstract interface (store, recall, forget) with MemoryEntry and MemoryCategory |
| `tiered_memory.py` | 3-tier memory: Hot (TTL cache), Warm (tag-indexed), Cold (relation-linked persistent) |
| `context.py` | Context builder assembling ExecutionContext from guard result, memories, and evidence |
| `evidence.py` | Evidence Pack generator producing auditable JSONL execution traces |
| `mcp_client.py` | MCP client communicating with ygn-core via stdio JSON-RPC 2.0 |
| `tool_bridge.py` | Bridge between MCP tools and the orchestrator's execution pipeline |
| `uacp.py` | Python uACP codec -- identical wire format to the Rust implementation |
| `evolution.py` | Evolution loop for scaffold self-modification with file whitelist and safety gates |
| `teaming.py` | Dynamic Teaming and Flow Control -- team formation, flow policies, distributed swarm |
| `vla_adapter.py` | VLA (Vision-Language-Action) adapter for bridging perception to hardware actions |
| `repl.py` | Simple interactive REPL for ygn-brain orchestrator |

---

## Tests

### Rust: 163 tests (160 unit + 3 smoke)

Unit tests are embedded in each source module (`#[cfg(test)]`). Integration tests:

| File | Description |
|------|-------------|
| `ygn-core/tests/smoke_test.rs` | End-to-end smoke tests across module boundaries |

### Python: 108 tests

| File | Description |
|------|-------------|
| `ygn-brain/tests/test_fsm.py` | FSM phase transitions and invalid transition rejection |
| `ygn-brain/tests/test_evidence.py` | EvidencePack creation, entry addition, JSONL serialization |
| `ygn-brain/tests/test_orchestrator.py` | Orchestrator pipeline run, guard integration, memory wiring |
| `ygn-brain/tests/test_guard.py` | Guard pipeline threat detection across 3 injection categories |
| `ygn-brain/tests/test_swarm.py` | Swarm modes, task analysis, and execution |
| `ygn-brain/tests/test_hivemind.py` | HiveMind 7-phase pipeline execution and phase results |
| `ygn-brain/tests/test_memory.py` | Memory service interface (store, recall, forget) |
| `ygn-brain/tests/test_context.py` | ContextBuilder assembly with guard and memory |
| `ygn-brain/tests/test_mcp_client.py` | MCP client JSON-RPC message formation and parsing |
| `ygn-brain/tests/test_vla.py` | VLA adapter input/output and stub implementation |
| `ygn-brain/tests/test_teaming.py` | Team formation, agent profiles, flow policies |
| `ygn-brain/tests/test_uacp.py` | uACP encode/decode round-trip for all 4 verbs |
| `ygn-brain/tests/test_tiered_memory.py` | 3-tier memory promotion, eviction, and tag queries |
| `ygn-brain/tests/test_evolution.py` | Evolution proposals, whitelist checks, safety guards |
| `ygn-brain/tests/test_smoke.py` | End-to-end smoke tests for the Python package |

---

## Configuration

| File | Purpose |
|------|---------|
| `Makefile` | Top-level quality gates: `test`, `lint`, `fmt`, `security`, `clean` |
| `ygn-core/Cargo.toml` | Rust crate manifest (dependencies: axum, tokio, serde, clap, rusqlite, etc.) |
| `ygn-core/rust-toolchain.toml` | Rust toolchain pinning |
| `ygn-brain/pyproject.toml` | Python package manifest (hatchling build, pydantic, opentelemetry, pytest/ruff/mypy dev deps) |
| `.github/workflows/ci-rust.yml` | CI workflow for Rust (fmt, clippy, test) |
| `.github/workflows/ci-python.yml` | CI workflow for Python (ruff, mypy, pytest) |
| `.github/workflows/security.yml` | Security scanning workflow |
| `.gitignore` | Git ignore rules |
| `CODEOWNERS` | Code ownership declarations |
| `LICENSE` | Project license |

## Documentation

| File | Purpose |
|------|---------|
| `README.md` | Project overview and quickstart |
| `CLAUDE.md` | Claude Code agent instructions |
| `AGENTS.md` | Multi-agent architecture documentation |
| `CONTRIBUTING.md` | Contribution guidelines |
| `INSTALL.md` | Installation instructions |
| `ROADMAP.md` | Project roadmap (M0-M8 and beyond) |
| `ROADMAP-02.md` | Extended roadmap |
| `TRADEMARK.md` | Trademark policy |

### Memory Bank

| File | Purpose |
|------|---------|
| `memory-bank/projectBrief.md` | Project brief and scope |
| `memory-bank/productContext.md` | Product context and goals |
| `memory-bank/systemPatterns.md` | System patterns and architecture decisions |
| `memory-bank/architect.md` | Architecture notes |
| `memory-bank/decisionLog.md` | Decision log |
| `memory-bank/activeContext.md` | Active context for current work |
| `memory-bank/progress.md` | Progress tracking |

### GitHub Chat Modes

| File | Purpose |
|------|---------|
| `.github/ask.chatmode.md` | Ask chatmode configuration |
| `.github/architect.chatmode.md` | Architect chatmode configuration |
| `.github/code.chatmode.md` | Code chatmode configuration |
| `.github/debug.chatmode.md` | Debug chatmode configuration |

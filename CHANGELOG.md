# Changelog

All notable changes to Y-GN (Yggdrasil-Grid Nexus) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-02-24

First public MVP release. Brain and Core are independently usable and
integrate over MCP (JSON-RPC 2.0 over stdio).

### Added

**ygn-core (Rust data-plane)**
- MCP server over stdio with `initialize`, `tools/list`, `tools/call`
- Built-in tools: `echo`, `hardware` (simulated drive/sense/look/speak)
- CLI: `status`, `gateway`, `config schema`, `tools list`, `providers list`,
  `mcp`, `registry list`, `registry self-info`, `skills list`, `diagnose`
- HTTP gateway (Axum): `/health`, `/providers`, `/health/providers`
- Multi-provider LLM: Claude, OpenAI, Gemini, Ollama via unified `Provider` trait
- Credential vault with zero-on-drop API key management
- Token-bucket rate limiter and circuit-breaker health tracking per provider
- Policy engine (Allow / Deny / RequireApproval) with full audit trail
- Process sandbox with 4 profiles: NoNet, Net, ReadOnlyFs, ScratchFs
- Landlock sandbox interface (Linux)
- Node registry with role/capability-based discovery
- Skills system with topological-sort execution
- SQLite memory engine with FTS5 and BM25 ranking
- Channel trait with CLI, Telegram, Discord, Matrix adapters
- Tunnel support: cloudflared, tailscale, ngrok
- uACP binary protocol for constrained edge nodes
- OpenTelemetry instrumentation
- Diagnostics engine for gate output analysis
- 336 tests (unit + integration)

**ygn-brain (Python control-plane)**
- Orchestrator (mediator pattern) with sync `run()` and async `run_async()`
- HiveMind 7-phase pipeline: diagnosis, analysis, planning, execution,
  validation, synthesis, completion
- HybridSwarmEngine with 6 modes: Parallel, Sequential, RedBlue, PingPong,
  LeadSupport, Specialist
- MCP client: subprocess spawn, JSON-RPC handshake, tool discovery and
  execution via `McpClient` and `McpToolBridge`
- GuardPipeline: prompt-injection detection (instruction override, role
  manipulation, data extraction)
- EvidencePack: auditable JSONL trace of every decision and tool call
- LLMProvider abstract interface with StubLLMProvider for testing
- ProviderRouter with prefix-based model routing and ModelSelector
- Interactive REPL (`ygn-brain-repl` command)
- Tiered memory: hot (TTL cache), warm (tag-indexed), cold (relation-linked)
- Dynamic teaming with AgentProfile and FlowPolicy
- VLA adapter for vision-language-action bridging
- Context compression, conversation tracking, personality system
- Event sourcing, DyLAN metrics, success memory
- OpenTelemetry hooks
- 244 tests (unit + async integration)

**Infrastructure**
- Makefile: `make test` (lint + test-rust + test-python), `make fmt`, `make lint`
- Cross-platform build support (Windows MSVC auto-detection)
- CI workflows: ci-rust.yml, ci-python.yml, security.yml
- INSTALL.md quickstart with 3 scenarios (CLI, Brain pipeline, MCP integration)
- Examples: `01_cli_tools.sh`, `02_brain_pipeline.py`, `03_mcp_integration.py`

### Fixed

- **MCP tools/call panic**: `handle_tools_call` created a nested tokio runtime
  inside `#[tokio::main]`, causing "Cannot start a runtime from within a
  runtime" panic. Now uses `Handle::try_current()` + `block_in_place` when an
  existing runtime is detected, with fallback to a new runtime otherwise.
- Echo tool parameter in docs and examples: corrected from `text` to `input`
  to match the actual `EchoTool` schema in ygn-core
- Mock MCP server in Python tests now mirrors the real ygn-core echo schema
  (`input` parameter with JSON Schema `required` field)
- REPL `async_main()` no longer falsely announces real provider usage when
  API keys are detected; clearly states StubLLMProvider is in use
- Makefile: cross-platform Windows MSVC target auto-detection for cargo commands

### Known Limitations

- Python-side LLM providers are stub-only; real Claude/OpenAI/Gemini/Ollama
  adapters exist in Rust but not yet in Python
- WASM/WASI sandbox is logical (profile-based access checks), not kernel-level
- Memory tiers use word-overlap matching, not vector embeddings
- Distributed registry is in-memory only (no shared persistent store)

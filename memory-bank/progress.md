# Progress

## Done

### M0 — Bootstrap (COMPLETE)
- [x] Monorepo structure (ygn-core/ Rust + ygn-brain/ Python)
- [x] Licensing (Apache-2.0), governance docs, CLAUDE.md, AGENTS.md
- [x] CI/CD (GitHub Actions for Rust + Python + Security) + Makefile
- [x] All quality gates green

### M1 — Core Usable (COMPLETE)
- [x] 8 trait-based subsystems: Provider, Channel, Tool, Memory, Observer, Security, Config, Gateway
- [x] StubProvider, CliChannel, EchoTool, NoopMemory, VerboseObserver, NoopSandbox
- [x] CLI: status, gateway, config schema, tools list, providers list
- [x] 44 Rust tests passing

### M2 — Brain Usable (COMPLETE)
- [x] GuardPipeline (prompt injection detection, 3 attack categories)
- [x] SwarmEngine (6 modes: Parallel/Sequential/RedBlue/PingPong/LeadSupport/Specialist)
- [x] HiveMindPipeline (7-phase execution with FSM + EvidencePack)
- [x] MemoryService + InMemoryBackend, ContextBuilder
- [x] Orchestrator rewired with real delegation
- [x] 32 Python tests passing

### M3 — Brain↔Core Integration (COMPLETE)
- [x] MCP Server (Rust): JSON-RPC 2.0 over stdio, initialize/tools/list/tools/call
- [x] MCP Client (Python): subprocess lifecycle, protocol handshake, McpToolBridge
- [x] End-to-end: Brain discovers and calls Core tools via MCP
- [x] 55 Rust + 44 Python tests

### M4 — Secure Tool Execution (COMPLETE)
- [x] ProcessSandbox: 4 profiles (NoNet/Net/ReadOnlyFs/ScratchFs), path traversal prevention
- [x] PolicyEngine: risk assessment + action decision (Allow/Deny/RequireApproval)
- [x] AuditLog: security trail with JSONL export
- [x] MCP server wired: policy + audit before every tool call
- [x] 93 Rust tests

### M5 — Memory v1 (COMPLETE)
- [x] SqliteMemory (Rust): FTS5 BM25, WAL mode, trigger-synced index
- [x] TieredMemoryService (Python): Hot (TTL) → Warm (tags) → Cold (relations)
- [x] Decay, promote, cross-tier recall, session filtering
- [x] 52 Python tests

### M6 — IoA Distributed + Embodiment (COMPLETE)
- [x] Registry & Discovery (Rust): InMemoryRegistry, NodeInfo, DiscoveryFilter, heartbeat
- [x] Dynamic Teaming (Python): TeamBuilder, FlowController (4 policies), DistributedSwarmEngine
- [x] µACP Codec: binary wire format (Rust + Python), cross-language interop verified
- [x] Hardware Simulator (Rust): SimulatedHardware (Drive/Sense/Look/Speak), HardwareTool via MCP
- [x] VLA Adapter (Python): StubVLAAdapter, VLABridge for MCP tool calls
- [x] 129 Rust + 85 Python tests

### M7 — Self-Healing + Self-Evolution (COMPLETE)
- [x] DiagnosticEngine (Rust): error classification (7 categories), fix suggestions, auto-heal
- [x] GateRunner + HealAction for automated build repair
- [x] EvolutionEngine (Python): scaffold evolution loop, FileWhitelist, SafetyGuard, dry-run
- [x] 160 Rust + 108 Python tests

### M8 — Release Ready (COMPLETE)
- [x] INSTALL.md: full installation guide + 3 quickstart scenarios
- [x] README.md: project overview, architecture diagram, features, milestones
- [x] 3 example scripts (CLI tools, Brain pipeline, MCP integration)
- [x] 7 Python smoke tests + 3 Rust integration smoke tests
- [x] 163 Rust + 108 Python tests — all gates green

### Post-MVP — Multi-Provider LLM (COMPLETE)
- [x] 4 provider adapters (Claude, OpenAI, Gemini, Ollama) with real HTTP API mapping
- [x] ProviderRegistry with model-name routing (claude-* → claude, gpt-* → openai, etc.)
- [x] Credential vault: secure API key management with zero-on-drop
- [x] Rate limiter: token-bucket per provider
- [x] Provider health: tracking + circuit breaker (5 consecutive failures)
- [x] Python LLMProvider ABC + StubLLMProvider
- [x] ProviderRouter + ModelSelector for task-based model selection
- [x] HiveMind.run_with_provider() for async LLM-backed pipeline
- [x] Orchestrator.run_async() for async orchestration
- [x] Event sourcing, SuccessMemory, Context compression, DyLAN metrics
- [x] Telegram, Discord, Matrix channels
- [x] Skills system with topological sort
- [x] OpenTelemetry (Rust + Python)

### Post-MVP — Full Coverage Sprint (COMPLETE)
- [x] Discord channel adapter with MockDiscordTransport
- [x] Matrix channel adapter with MockMatrixTransport
- [x] Gateway enhanced: GET /providers + GET /health/providers
- [x] SwarmEngine.execute_with_provider() — async LLM-backed swarm modes
- [x] Interactive REPL (sync + async modes)
- [x] Landlock OS sandbox — cross-platform abstraction (enforced on Linux)
- [x] TunnelManager — cloudflared/tailscale/ngrok lifecycle management
- [x] ConversationMemory — multi-turn context window management
- [x] AgentPersonality + PersonalityRegistry — 4 built-in agent personas
- [x] Capability matrix: 0 Planned items remaining

### v0.1.0 MVP Release (2026-02-24)
- [x] Fixed MCP tools/call nested runtime panic (block_in_place)
- [x] Fixed echo tool argument schema in docs/examples/tests (text → input)
- [x] Fixed REPL async_main() false provider announcements
- [x] Fixed Makefile for Windows MSVC cross-platform builds
- [x] Added echo schema regression test
- [x] Created CHANGELOG.md
- [x] Updated README.md with release section
- [x] E2E demo verified: McpClient → ygn-core mcp → echo tool → response

### v0.2.0 — CLI LLM Providers (2026-02-24)
- [x] CodexCliProvider: subprocess LLM via codex exec
- [x] GeminiCliProvider: subprocess LLM via gemini CLI
- [x] ProviderFactory: deterministic provider selection from YGN_LLM_PROVIDER env
- [x] 52 new tests for providers and factory
- [x] Orchestrator uses ProviderFactory when no provider given

### v0.2.1 — Windows E2E + Bug Fixes (2026-02-25)
- [x] Windows .CMD subprocess support for CLI providers
- [x] Codex JSONL output parsing fix
- [x] Version alignment: 0.1.0 → 0.2.1 across all manifests
- [x] Fix: model="default" hardcode in HiveMind + Swarm (5 locations)
- [x] Fix: ModelSelector stale Claude fallback → gpt-5.2-codex
- [x] Fix: EvidenceKind StrEnum constrains valid kinds
- [x] Fix: HiveMind phase_timeout with asyncio.wait_for + graceful fallback
- [x] README fact-first rewrite with "Works Today" vs "Known Stubs"
- [x] New ygn-core/README.md
- [x] 14 new tests: model capture, timeout, evidence kind, guard gaps
- [x] Known gaps documented: guard regex bypass, WASM stub, Landlock stub

### Known Bugs (all fixed in v0.2.1)
- [FIXED] model="default" sent to LLM providers instead of actual model name
- [FIXED] ModelSelector fallback used stale "claude-3-5-sonnet-20241022"
- [FIXED] EvidenceEntry.kind accepted arbitrary strings
- [FIXED] No timeout on HiveMind LLM phases (Gemini hangs on 3rd call)

## Summary

All milestones M0–M8 + Post-MVP complete. **v0.2.1 released 2026-02-25.**
Total: **336 Rust tests + 313+ Python tests = 649+ tests**, all green.

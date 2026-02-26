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

### v0.7.0 — Hardening Sprint "Truth & Wiring" (2026-02-26)
- [x] Phase 1: README fact-first rewrite, version alignment to 0.7.0
- [x] Phase 2: Codex default model gpt-5.2-codex → gpt-5.3-codex, orchestrate_refined wired to real MultiProviderGenerator
- [x] Phase 3: GET /guard/log reads from ~/.ygn/guard_log.db, GET /sessions scans real JSONL, GuardLog class
- [x] Phase 4: MCP -32600 Invalid Request error code, Accept header awareness
- [x] GuardLog exported from ygn_brain
- [x] 7 new Rust tests + 3 new Python tests

### v0.6.0 — Refinement Harness (2026-02-26)
- [x] Harness types: Candidate, Feedback, HarnessConfig, HarnessResult, POETIQ_PRESET
- [x] Verifier ABC + TextVerifier + CommandVerifier
- [x] CandidateGenerator ABC + StubCandidateGenerator + MultiProviderGenerator
- [x] DefaultPolicy + ConsensusSelector (score + consensus bonus)
- [x] HarnessMemoryStore (pattern capitalization in TieredMemory)
- [x] RefinementHarness engine (generate-verify-refine loop)
- [x] orchestrate_refined MCP tool + harness exports
- [x] E2E tests with real Codex + Gemini CLI
- [x] Drift fixes: README v0.2.1→v0.5.0, MCP version 0.3.0→dynamic

### v0.5.0 — Production-Ready (2026-02-26)
- [x] Track A: guard_download.py CLI for PromptGuard-86M model download
- [x] Track A: entity_extraction.py — EntityExtractor ABC + RegexEntityExtractor for Temporal KG
- [x] Track A: Temporal KG relation index, recall_by_relation(), recall_multihop()
- [x] Track A: PhaseResult dataclass for HiveMind phase tracking
- [x] Track A: Codex CLI hardening — is_available(), Windows .CMD lookup, robust JSONL parsing
- [x] Track B: GET /guard/log, GET /sessions, GET /memory/stats gateway endpoints
- [x] Track B: SqliteTaskStore — persistent A2A task store
- [x] Track B: Dashboard wired to live API (all 5 pages), auto-refresh, connection indicator
- [x] E2E: golden_path.py demo + 11 integration tests
- [x] 39 new Python tests + 6 new Rust tests

### v0.4.0 — Observable Governance (2026-02-26)
- [x] Section 1: Vector Embeddings — EmbeddingService ABC, Stub/Ollama/Local backends, cosine similarity, TieredMemory integration, Rust hybrid recall
- [x] Section 2: Persistent Registry — SqliteRegistry, heartbeat eviction, cross-node sync, /registry/nodes API
- [x] Section 3: ML Guard — OnnxClassifierGuard, OllamaClassifierGuard, pipeline fast-path, GuardStats, benchmark suite
- [x] Section 4: Governance Dashboard — ygn-dash Tauri app with 5 pages (Dashboard, GuardLog, Evidence, Nodes, Memory)
- [x] 35 new Python tests + 23 new Rust tests

### v0.3.0 — Compliance, Security, Interoperability (2026-02-25)
- [x] A1: Evidence Pack Crypto — SHA-256 hash chain, ed25519 signing, RFC 6962 Merkle tree (EU AI Act Art. 12)
- [x] A3: Guard v2 — GuardBackend ABC, RegexGuard rename, ToolInvocationGuard (whitelist + rate limit + Log-To-Leak), scoring, ClassifierGuard stub
- [x] B3: Red/Blue Executor — 10-template sync mode + LLM adversarial async mode (EU AI Act Art. 9)
- [x] B1: Brain MCP Server — JSON-RPC 2.0 over stdio, 5 tools (orchestrate, guard_check, evidence_export, swarm_execute, memory_recall)
- [x] A2: Wassette Sandbox — WassetteSandbox struct, policy mapping, fallback to ProcessSandbox
- [x] A4: MCP Streamable HTTP — handle_jsonrpc() refactor, POST /mcp route, SSE stub
- [x] B2: A2A Agent Cards — GET /.well-known/agent.json, POST /a2a (SendMessage, GetTask, ListTasks)
- [x] 23 new Python tests + 11 new Rust tests
- [x] pynacl>=1.5.0 dependency added
- [x] ruff clean, all tests green

## Summary

All milestones M0–M8 + Post-MVP + v0.7.0 complete. **v0.7.0 released 2026-02-26.**
Total: **380 Rust tests + 445 Python tests = 825 tests**, all green.

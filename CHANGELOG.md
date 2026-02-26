# Changelog

All notable changes to Y-GN (Yggdrasil-Grid Nexus) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.6.0] — 2026-02-26

### Added — Refinement Harness (Poetiq-inspired)

#### Core Engine
- `RefinementHarness` — generic generate-verify-refine loop engine
- `CandidateGenerator` ABC + `StubCandidateGenerator` + `MultiProviderGenerator`
- `Verifier` ABC + `TextVerifier` (heuristic quality) + `CommandVerifier` (shell command)
- `RefinementPolicy` ABC + `DefaultPolicy` (max_rounds + min_score)
- `Selector` ABC + `ConsensusSelector` (score + multi-provider agreement bonus)
- `HarnessMemoryStore` — capitalizes winning patterns in TieredMemoryService
- `POETIQ_PRESET` — default config for Poetiq-style ensemble refinement

#### Integration
- `orchestrate_refined` MCP tool in Brain server (7th tool)
- E2E tests with real Codex + Gemini CLI providers

### Fixed
- README.md version drift: v0.2.1 → v0.5.0
- MCP serverInfo.version drift: "0.3.0" → dynamic from `__version__`

## [0.5.0] — 2026-02-26

### Added

#### Track A — Python/Brain Production Hardening
- `guard_download.py` — CLI tool (`ygn-brain-guard-download`) to download PromptGuard-86M from HuggingFace
- `entity_extraction.py` — EntityExtractor ABC + RegexEntityExtractor for Temporal KG
- Temporal Knowledge Graph: relation index, `recall_by_relation()`, `recall_multihop()` on TieredMemoryService
- `PhaseResult` dataclass for HiveMind phase tracking (status, output, latency_ms)
- Codex CLI hardening: `is_available()`, Windows .CMD lookup, robust JSONL parsing

#### Track B — Rust/Dashboard Production Wiring
- `GET /guard/log` — paginated guard decision log endpoint
- `GET /sessions` — Evidence Pack sessions list endpoint
- `GET /memory/stats` — memory tier distribution endpoint
- `SqliteTaskStore` — persistent A2A task store (replaces in-memory)
- Dashboard wired to live API data (all 5 pages)
- Auto-refresh (10s polling) on Dashboard and GuardLog
- Connection indicator (green/red dot) in sidebar
- Additional API client functions: `fetchGuardLog`, `fetchSessions`, `fetchMemoryStats`

#### E2E
- `examples/golden_path.py` — full stack demo: Guard → Orchestrate → Evidence → Verify
- 11 E2E integration tests

## [0.4.0] — 2026-02-26

### Added

#### Section 1: Vector Embeddings
- `EmbeddingService` ABC with `embed()` and `dimension()` abstract methods
- `StubEmbeddingService` for testing without ML dependencies
- `OllamaEmbeddingService` — embeddings via Ollama `/api/embeddings` endpoint
- `LocalEmbeddingService` — local CPU inference via sentence-transformers (all-MiniLM-L6-v2)
- `cosine_similarity()` function (Python + Rust)
- TieredMemoryService now accepts optional `EmbeddingService` for semantic recall
- Rust `SqliteMemory` — `embedding BLOB` column, `store_with_embedding()`, `recall_with_embedding()` with hybrid BM25+cosine ranking (0.7/0.3 weighting)
- `memory_search_semantic` MCP tool in Brain server

#### Section 2: Persistent Registry
- `SqliteRegistry` — SQLite-backed `NodeRegistry` implementation with WAL mode
- Background heartbeat eviction (`evict_stale()`)
- Cross-node registry sync (`merge_nodes()`, `POST /registry/sync`)
- `GET /registry/nodes` API endpoint
- Dynamic Agent Card version from `CARGO_PKG_VERSION`

#### Section 3: ML-Based Guard
- `OnnxClassifierGuard` — ONNX Runtime inference with stub mode for CI
- `OllamaClassifierGuard` — Ollama chat completion with classification prompt
- GuardPipeline integration: regex fast-path (skip ML when regex blocks)
- `GuardStats` — guard check statistics tracking
- Guard benchmark suite: regex catches 5/10 attack templates (50% coverage)

#### Section 4: Governance Dashboard (ygn-dash)
- New Tauri 2 + React + TypeScript + Tailwind CSS v4 desktop app
- Dashboard page: status cards, provider health grid
- Guard Log page: filterable timeline with threat level badges
- Evidence Viewer page: session browser + hash chain visualization
- Node Registry page: node table with role filter
- Memory Explorer page: tier distribution chart + BM25/semantic search toggle

### Dependencies
- Python optional: `sentence-transformers>=3.0.0`, `onnxruntime>=1.18.0`, `transformers>=4.40.0` (under `[ml]` extra)
- Dashboard: Tauri 2, React 19, react-router-dom 6, Recharts 3, Tailwind CSS v4

## [0.3.0] - 2026-02-25

Compliance, Security, Interoperability — EU AI Act readiness, guard v2,
adversarial testing, Brain MCP server, A2A agent cards.

### Added

- **Evidence Pack Crypto (A1)**: SHA-256 hash chain linking entries, ed25519
  signing via pynacl, RFC 6962 Merkle tree root. EU AI Act Art. 12 fields:
  `start_time`, `end_time`, `model_id`, `signer_public_key`, `merkle_root`.
  Time-sortable `entry_id` (UUIDv7-like). Backward compatible — all new fields
  have defaults.
- **Guard v2 Interface (A3)**: `GuardBackend` ABC with `check()` → `GuardResult`
  (now includes `score: float`). `RegexGuard` (renamed from `InputGuard`, alias
  kept). `ToolInvocationGuard` with tool whitelist, per-session rate limit, and
  Log-To-Leak detection. `ClassifierGuard` ABC stub in `guard_backends.py` for
  future ML integration (LlamaFirewall path documented).
- **Red/Blue Executor (B3)**: `RedBlueExecutor` sync mode with 10 attack
  templates. `SwarmEngine._run_red_blue()` async mode using LLM provider as red
  agent. Results formatted as EU AI Act Art. 9 adversarial testing evidence.
- **Brain MCP Server (B1)**: `McpBrainServer` class exposing 5 tools via
  JSON-RPC 2.0 over stdio: `orchestrate`, `guard_check`, `evidence_export`,
  `swarm_execute`, `memory_recall`. CLI entry: `ygn-brain-mcp`.
- **Wassette Sandbox (A2)**: `WassetteSandbox` with policy mapping (Y-GN
  profiles → Wassette permission flags), availability check, automatic fallback
  to `ProcessSandbox`.
- **MCP Streamable HTTP (A4)**: `handle_jsonrpc()` extracted as reusable
  `Value → Value` handler. `POST /mcp` gateway route for HTTP transport.
- **A2A Agent Cards (B2)**: `GET /.well-known/agent.json` returns Agent Card
  with skills and interfaces. `POST /a2a` handles `SendMessage`, `GetTask`,
  `ListTasks`.
- 23 new Python tests, 11 new Rust tests (680 total, all green).
- `pynacl>=1.5.0` dependency.

## [0.2.1] - 2026-02-25

Post-audit overhaul — fact-first documentation, 4 bug fixes, real E2E verification.
Version alignment across all manifests (was 0.1.0, now 0.2.1).

### Fixed

- **HiveMind model="default" hardcode**: `run_with_provider()` sent literal
  `"default"` as model name to LLM providers. Now uses
  `getattr(provider, '_model', None) or provider.name()`. Same fix applied
  to SwarmEngine at 4 locations.
- **ModelSelector stale fallback**: default model fallback referenced
  `claude-3-5-sonnet-20241022` (stale). Changed to `gpt-5.2-codex`.
- **EvidenceEntry kind unconstrained**: `kind: str` accepted any string.
  Added `EvidenceKind(StrEnum)` with 6 valid values: input, decision,
  tool_call, source, output, error. Invalid kinds now raise ValidationError.
- **HiveMind phase timeout**: async pipeline had no per-phase timeout,
  causing Gemini CLI to hang on 3rd LLM call. Added `phase_timeout` param
  with `asyncio.wait_for()` + graceful fallback on timeout.
- **Windows .CMD subprocess support**: `asyncio.create_subprocess_exec`
  cannot execute npm-installed `.CMD` batch scripts on Windows. Both
  `CodexCliProvider` and `GeminiCliProvider` now detect `.CMD`/`.BAT`
  executables and use `create_subprocess_shell` with `list2cmdline` quoting.
- **Codex JSONL output parsing**: `codex exec --json` produces structured
  JSONL events. New `_parse_jsonl_response()` extracts `agent_message`
  text and `turn.completed` token usage instead of capturing raw noisy
  stdout.
- **Codex `--full-auto` flag**: prevents the agent from hanging on
  interactive approval prompts when run as a subprocess.
- **Codex default model**: corrected from `gpt-5.3-codex` to
  `gpt-5.2-codex` (matching actual Codex CLI default).
- **Version alignment**: pyproject.toml, Cargo.toml, __init__.py all now
  report 0.2.1 (were stuck at 0.1.0).

### Added

- `EvidenceKind` StrEnum exported from `ygn_brain`.
- `phase_timeout` parameter on `HiveMindPipeline.run_with_provider()`.
- `YGN_PHASE_TIMEOUT_SEC` env var for default phase timeout.
- 14 new tests: model capture, phase timeout, evidence kind constraint,
  JSONL 7-phase validation, guard known-gap documentation tests.
- `ygn-core/README.md` — crate-level documentation.

### Changed

- **README.md**: fact-first rewrite with "Works Today (E2E verified)" vs
  "Roadmap / Known Stubs" sections.
- **ROADMAP.md**: added Post-0.2 Priorities (P1-P7) section.
- **CLAUDE.md**: corrected test counts, documented stubs.
- **memory-bank**: updated activeContext, progress, decisionLog.
- Total: 336 Rust + 313 Python = 649 tests.

## [0.2.0] - 2026-02-24

CLI LLM providers — real inference via Codex and Gemini CLIs, no API cost.

### Added

- **CodexCliProvider**: LLM inference via `codex exec` subprocess. Uses
  existing Codex CLI authentication (subscription-based). Default model
  `gpt-5.2-codex`, configurable via `YGN_CODEX_MODEL`.
- **GeminiCliProvider**: LLM inference via `gemini` CLI subprocess with
  JSON output parsing. Default model `gemini-3.1-pro-preview`, configurable
  via `YGN_GEMINI_MODEL`.
- **ProviderFactory**: Deterministic provider selection from `YGN_LLM_PROVIDER`
  env var (`codex` | `gemini` | `stub`). Optional auto-fallback mode.
- **Timeout control**: `YGN_LLM_TIMEOUT_SEC` env var (default 300s) for both
  CLI providers.
- 52 new tests for providers and factory (16 codex + 19 gemini + 17 factory).

### Changed

- **Orchestrator** now uses `ProviderFactory.create()` when no provider is
  given explicitly (was: raise RuntimeError). Always has a working provider.
- **ProviderRouter** prefix map: `gpt-*`, `o1-*`, `o3-*`, `o4-*` now route
  to `codex` provider (was: `openai`).
- **ModelSelector** default models: all complexity levels default to
  `gpt-5.2-codex` (was: Claude models). Gemini preferred provider returns
  `gemini-3.1-pro-preview`.
- **REPL** `async_main()` uses `ProviderFactory` and displays the resolved
  provider name and model clearly.
- **Example 02** displays which provider is in use and respects
  `YGN_LLM_PROVIDER`.

### Fixed

- Example 02 evidence printing: `event_type` -> `kind` (matching the actual
  `EvidenceEntry` field name).

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

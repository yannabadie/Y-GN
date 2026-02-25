# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Current version: v0.2.1**

Y-GN (Yggdrasil-Grid Nexus) is a distributed multi-agent runtime that separates **reasoning** from **execution**:

- **ygn-brain/** (Python) — cognitive control-plane: planning, multi-agent orchestration (HiveMind 7-phase pipeline, HybridSwarmEngine), governance, Evidence Packs, scoring. Extracted from NEXUS NX-CG.
- **ygn-core/** (Rust workspace) — data-plane: tool execution, channels, tunnels, WASM/WASI sandboxing, memory engine, hardware. Extracted from ZeroClaw (do NOT reuse ZeroClaw branding — trademark restriction).

The Brain↔Core contract uses **MCP** (Model Context Protocol) as primary integration, with optional HTTP fallback and µACP for constrained edge nodes.

## Build & Test Commands

### Rust (ygn-core)
```bash
cargo build -p ygn-core
cargo fmt --check
cargo clippy -- -D warnings
cargo test
```

### Python (ygn-brain)
```bash
python -m compileall .
pytest -q
ruff check .
mypy .
```

### Full gate (both)
```bash
make test    # or: just test
```

### Security scans
```bash
# Rust: cargo-deny for dependency audit
# Python: pip-audit + secret scan
# Sandbox escape tests + SSRF/path-traversal/prompt-injection regression suite
```

### CLI commands (ygn-core)
```bash
ygn-core status                # Show node status
ygn-core gateway --bind 0.0.0.0:3000  # Start HTTP gateway
ygn-core config schema         # Export config JSON schema
ygn-core tools list            # List registered tools
ygn-core providers list        # List registered LLM providers
ygn-core skills list           # List registered skills
ygn-core mcp                   # Start MCP server over stdio
ygn-core registry list         # List registered nodes
ygn-core registry self-info    # Show this node's info
ygn-core diagnose              # Run diagnostics on stdin
```

### Gateway HTTP routes
- `GET /health` — Service health check
- `GET /providers` — List all configured LLM providers with capabilities
- `GET /health/providers` — Health status of all providers (circuit breaker state)

### Test counts
- Rust (ygn-core): 336 tests
- Python (ygn-brain): 299 tests
- Total: 635 tests

## Architecture

### Brain↔Core separation
```
User/Channel → ygn-core (gateway/Axum) → MCP call → ygn-brain (orchestrator)
                                        ← MCP response ←
ygn-brain plans → tool calls via MCP → ygn-core executes in WASM/WASI sandbox
```

Brain can run in cloud; Core can run on edge. Multiple nodes form an "Internet of Agents" (IoA) mesh via registry + discovery.

### ygn-brain internals
The former monolithic `OrchestratorV7` is decomposed into:
- **StateMachineHandler** — FSM transitions
- **TaskRouter** — dispatches to swarm executors
- **ContextBuilder** — assembles context for LLM calls
- **GuardPipeline** — security/validation guards
- **TaskExecutor** — runs the plan
- **EvidencePackGenerator** — produces auditable JSONL trace (inputs, decisions, tool calls, sources, outputs, telemetry IDs)

Swarm modes: Parallel, Sequential, RedBlue, PingPong, LeadSupport, Specialist.

LLM integration:
- **LLMProvider** — abstract base class for provider adapters (StubLLMProvider for testing)
- **ProviderRouter** — routes tasks to appropriate models based on ModelSelector policies
- **HiveMind.run_with_provider()** — async LLM-backed pipeline execution
- **Orchestrator.run_async()** — async orchestration with provider support

### Multi-Provider LLM Architecture
Y-GN supports 4 LLM providers via a unified `Provider` trait:
- **Claude** (Anthropic Messages API) — `claude-*` models
- **OpenAI** (Chat Completions API) — `gpt-*`, `o1-*`, `o3-*`, `o4-*`, `chatgpt-*` models
- **Gemini** (Google Generative AI API) — `gemini-*` models
- **Ollama** (local inference) — `llama3`, `mistral`, etc.

Key Rust modules:
- `multi_provider.rs` — ClaudeProvider, OpenAIProvider, GeminiProvider, OllamaProvider, ProviderRegistry
- `credential_vault.rs` — Secure API key management with zero-on-drop
- `rate_limiter.rs` — Token-bucket per-provider rate limiting
- `provider_health.rs` — Health tracking + circuit breaker (5 consecutive failures)

Key Python modules:
- `provider.py` — LLMProvider ABC + StubLLMProvider
- `provider_router.py` — ProviderRouter + ModelSelector for task-based model selection
- `hivemind.py` — HiveMind.run_with_provider() for async LLM-backed pipeline
- `orchestrator.py` — Orchestrator.run_async() for async orchestration

### ygn-core internals
Trait-based subsystems: `providers`, `channels`, `tools`, `memory`, `security`, `runtime`. Key components:
- CLI + daemon + gateway (Axum) with `/health`, `/providers`, `/health/providers` routes
- Multi-provider LLM: ClaudeProvider, OpenAIProvider, GeminiProvider, OllamaProvider + ProviderRegistry
- Credential vault (zero-on-drop), rate limiter (token-bucket), provider health (circuit breaker)
- Channels (Telegram, Discord, Matrix) + tunnels (cloudflared, tailscale, ngrok)
- WASM/WASI sandbox with profiles: `no-net`, `net`, `read-only-fs`, `scratch-fs` — **note:** process-level policy checks only; no wasmtime runtime is embedded
- Memory engine (SQLite) + caches
- Skills system with topological sort execution
- Config with JSON schema export; fields `ygn.node_role` (edge/core/brain-proxy) and `trust_tier`

### Memory subsystem (3-tier)
- **Hot** — semantic/TTL cache for recent interactions
- **Warm** — temporal index + hierarchical tags (SwiftMem-inspired)
- **Cold** — Temporal Knowledge Graph (Zep/Graphiti-inspired) + doc store; HippoRAG mode (KG + Personalized PageRank) for multi-hop reasoning. **Note:** `relations` table is declared but never populated; search uses word-overlap scoring, not vector embeddings

### Security model ("multi-wall")
WASM/WASI sandbox (process-level policy checks) → OS sandbox (Landlock types exist but `apply_linux()` is a stub — not enforced) → action allowlists/RBAC → runtime behavior analysis (HeteroGAT-Rank) → approval gates for HIGH-RISK actions.

## Agent Team Roles

When working as a subagent, identify your role from ROADMAP.md:
- **@RustCoreLead** — ygn-core, gateway, channels, runtime, config, release
- **@PyBrainLead** — ygn-brain, orchestration, swarm, evidence, governance
- **@SecurityLead** — sandbox, policies, supply-chain, threat-model
- **@MemoryLead** — sqlite/fts/vector, temporal KG, SwiftMem indexing, benchmarks
- **@ObservabilityLead** — OpenTelemetry, metrics, profiling, dashboards
- **@DocsReleaseLead** — ROADMAP, DECISIONS, user docs, release checklist

## Coordination Rules

- **1 worktree per epic** — no concurrent edits on the same files across epics
- **TDD mandatory** — no business code without tests (pytest / cargo test)
- **Stop-the-line** if any quality gate fails
- **Decision Log** (`memory-bank/decisionLog.md`) — append every non-trivial decision with date + rationale
- No cross-epic refactors unless agreed in Decision Log

## Memory Bank

The `memory-bank/` directory persists project context across sessions:
- `productContext.md` — project overview, tech stack
- `activeContext.md` — current focus, blockers
- `progress.md` — done / doing / next
- `decisionLog.md` — append-only decision table
- `systemPatterns.md` — recurring patterns, conventions

Always read these files at session start. Update them when significant changes occur (format: `[YYYY-MM-DD HH:MM:SS] - summary`). The command "UMB" triggers a full memory bank sync.

## Milestone Sequence

M0 (Bootstrap) → M1 (Core usable) → M2 (Brain usable) → M3 (Brain↔Core integration) → M4 (Secure sandbox) → M5 (Memory v1) → M6 (IoA distributed) → M7 (Self-healing) → M8 (Release) → Post-MVP (Multi-Provider LLM)

All milestones complete (current release: v0.2.1). The ROADMAP.md YAML block is the authoritative source for epic/task details and acceptance criteria.

## Key Constraints

- ZeroClaw is MIT+Apache-2.0 dual-licensed with trademark protection — never use the "ZeroClaw" brand in Y-GN output or naming
- NEXUS NX-CG code is proprietary — re-licensing required before importing; do not include UI/React or legacy API
- OpenTelemetry traces must be emitted on both happy-path and error-path (Brain + Core)
- Evidence Packs attach to every meaningful execution for auditability

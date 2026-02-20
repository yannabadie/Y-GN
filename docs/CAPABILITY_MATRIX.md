# Capability Matrix — Y-GN

Maps capabilities from upstream sources to Y-GN target modules.

**Action values:**
- `Keep` — used as-is from source
- `Merge` — combined from both sources
- `Adapt` — rewritten or wrapped for Y-GN
- `Drop` — not needed in Y-GN
- `Planned` — not yet implemented

| # | Capability | Source | Action | Notes | Target Module |
|---|-----------|--------|--------|-------|---------------|
| 1 | FSM (11 states) | NEXUS | Adapt | Simplified to 8 phases | ygn-brain/fsm.py |
| 2 | HiveMind 7-phase pipeline | NEXUS | Keep | Core orchestration pipeline | ygn-brain/hivemind.py |
| 3 | OrchestratorV7 (god-object) | NEXUS | Adapt | Decomposed into Mediator pattern | ygn-brain/orchestrator.py |
| 4 | HybridSwarmEngine (6 modes) | NEXUS | Keep | Parallel/Sequential/RedBlue/PingPong/LeadSupport/Specialist | ygn-brain/swarm.py |
| 5 | InputGuard (prompt injection) | NEXUS | Keep | 3 attack categories | ygn-brain/guard.py |
| 6 | GuardPipeline | NEXUS | Keep | Composable guard chain | ygn-brain/guard.py |
| 7 | TieredValidator | NEXUS | Drop | Replaced by guard pipeline | - |
| 8 | Evidence Pack | NEXUS | Keep | JSONL trace format | ygn-brain/evidence.py |
| 9 | Memory backends (hybrid) | NEXUS | Adapt | 3-tier (hot/warm/cold) | ygn-brain/tiered_memory.py |
| 10 | Context compression | NEXUS | Keep | 4 strategies (truncate/sliding_window/priority/summarize) | ygn-brain/context_compression.py |
| 11 | MCP client | NEXUS | Adapt | Async subprocess MCP client | ygn-brain/mcp_client.py |
| 12 | OpenTelemetry | NEXUS | Keep | YgnTracer + SpanGuard (Rust + Python) | ygn-core/telemetry.rs, ygn-brain/telemetry.py |
| 13 | Analytics dashboard | NEXUS | Drop | Post-MVP | - |
| 14 | React UI | NEXUS | Drop | Out of scope | - |
| 15 | REST API (Cerebro) | NEXUS | Drop | MCP replaces HTTP for tools | - |
| 16 | Agent drivers (Gemini/Claude) | NEXUS | Keep | 4 providers (Claude/OpenAI/Gemini/Ollama) + ProviderRegistry | ygn-core/multi_provider.rs, ygn-brain/provider.py |
| 17 | SuccessMemory | NEXUS | Keep | Past solutions store with best_mode_for() | ygn-brain/success_memory.py |
| 18 | DyLAN metrics | NEXUS | Keep | DyLANTracker with rank/prune | ygn-brain/dylan_metrics.py |
| 19 | Event sourcing | NEXUS | Keep | FSMEvent + InMemoryEventStore with replay/snapshot | ygn-brain/event_sourcing.py |
| 20 | CLI + daemon | ZeroClaw | Adapt | CLI with 8 subcommands | ygn-core/main.rs |
| 21 | Gateway (Axum) | ZeroClaw | Keep | HTTP gateway with /health | ygn-core/gateway.rs |
| 22 | Config + JSON schema | ZeroClaw | Keep | NodeConfig with schema export | ygn-core/config.rs |
| 23 | Provider trait | ZeroClaw | Adapt | Async trait + StubProvider | ygn-core/provider.rs |
| 24 | Channel trait | ZeroClaw | Adapt | CliChannel only (no real channels) | ygn-core/channel.rs |
| 25 | Tool trait + registry | ZeroClaw | Keep | EchoTool + HardwareTool | ygn-core/tool.rs |
| 26 | Memory trait + SQLite | ZeroClaw | Keep | FTS5 BM25, WAL mode | ygn-core/sqlite_memory.rs |
| 27 | Observer trait | ZeroClaw | Keep | VerboseObserver + NoopObserver | ygn-core/observer.rs |
| 28 | Security (credential scrub) | ZeroClaw | Keep | Regex-based redaction | ygn-core/security.rs |
| 29 | Sandbox profiles | ZeroClaw | Adapt | 4 profiles, path traversal prevention | ygn-core/sandbox.rs |
| 30 | Landlock (OS sandbox) | ZeroClaw | Adapt | Cross-platform abstraction, enforced on Linux only | ygn-core/landlock.rs |
| 31 | Channels (Telegram/Discord/Matrix) | ZeroClaw | Adapt | Telegram + Discord + Matrix channels | ygn-core/telegram.rs, ygn-core/discord.rs, ygn-core/matrix.rs |
| 32 | Tunnels (cloudflared/tailscale) | ZeroClaw | Adapt | TunnelManager with cloudflared/tailscale/ngrok stubs | ygn-core/tunnel.rs |
| 33 | Hardware/peripherals | ZeroClaw | Adapt | SimulatedHardware + HardwareTool | ygn-core/hardware.rs |
| 34 | Skills system | ZeroClaw | Keep | SkillDefinition + SkillRegistry + SkillExecutor (topo sort) | ygn-core/skills.rs |
| 35 | uACP codec | Y-GN | Keep | Binary wire format, Rust+Python | ygn-core/uacp.rs, ygn-brain/uacp.py |
| 36 | Node registry | Y-GN | Keep | InMemoryRegistry + discovery | ygn-core/registry.rs |
| 37 | Dynamic teaming | Y-GN | Keep | TeamBuilder + FlowController | ygn-brain/teaming.py |
| 38 | VLA adapter | Y-GN | Keep | StubVLAAdapter + VLABridge | ygn-brain/vla_adapter.py |
| 39 | DiagnosticEngine | Y-GN | Keep | Error classification + auto-heal | ygn-core/diagnostics.rs |
| 40 | EvolutionEngine | Y-GN | Keep | Scaffold evolution loop | ygn-brain/evolution.py |
| 41 | Policy engine | Y-GN | Keep | Risk assessment + decisions | ygn-core/policy.rs |
| 42 | Audit log | Y-GN | Keep | JSONL security trail | ygn-core/audit.rs |
| 43 | Credential vault | Y-GN | Keep | Secure API key management with zero-on-drop | ygn-core/credential_vault.rs |
| 44 | Rate limiter | Y-GN | Keep | Token-bucket per-provider rate limiting | ygn-core/rate_limiter.rs |
| 45 | Provider health | Y-GN | Keep | Health tracking + circuit breaker | ygn-core/provider_health.rs |
| 46 | Provider routing (Python) | Y-GN | Keep | ProviderRouter + ModelSelector | ygn-brain/provider_router.py |
| 47 | LLM-backed pipeline | Y-GN | Keep | HiveMind.run_with_provider + Orchestrator.run_async | ygn-brain/hivemind.py, orchestrator.py |

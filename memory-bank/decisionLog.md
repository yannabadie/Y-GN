# Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-19 | Y-GN licensed under Apache-2.0 | Compatible with ZeroClaw dual MIT/Apache-2.0. Permissive, allows commercial use, patent grant. Standard for Rust+Python ecosystems. |
| 2026-02-19 | NEXUS NX-CG code re-licensed Apache-2.0 for Y-GN | Original author (yannabadie) consents to re-license extracted components. Only brain-relevant modules imported (FSM, HiveMind, Swarm, Guards, Telemetry, Evidence). UI/API/legacy excluded. |
| 2026-02-19 | ZeroClaw branding prohibited in Y-GN | Per ZeroClaw trademark notice. Architectural patterns and code used under MIT/Apache-2.0, but the name "ZeroClaw" must not appear in binaries, docs, or marketing. Attribution in source comments only. |
| 2026-02-19 | MCP-first for Brain↔Core integration | MCP (Model Context Protocol) chosen as primary tool-call protocol. Aligns with ecosystem tooling. HTTP fallback available. µACP reserved for constrained edge (feature-flagged). |
| 2026-02-19 | Monorepo structure: ygn-core/ (Rust) + ygn-brain/ (Python) | Clean separation of data-plane (Rust) and control-plane (Python). Enables independent deployment (core on edge, brain in cloud). Single repo simplifies CI and cross-component testing. |
| 2026-02-19 | Trait-based subsystem architecture for ygn-core | Adopted ZeroClaw pattern: Provider, Channel, Tool, Memory, Observer, Sandbox as swappable traits with factory functions. Enables runtime polymorphism and testability via NoOp/Stub impls. |
| 2026-02-19 | OrchestratorV7 decomposed into Mediator pattern | NEXUS god-object split into: GuardPipeline, ContextBuilder, HiveMindPipeline, SwarmEngine, EvidencePack. Each component independently testable. Orchestrator acts as lightweight coordinator. |
| 2026-02-19 | MCP transport: JSON-RPC 2.0 over stdio | Simplest possible transport for v1. Core spawned as subprocess by Brain. Line-delimited JSON. Future: HTTP/SSE transport for networked deployments. |
| 2026-02-19 | Credential scrubbing in all tool outputs | Regex-based redaction of Bearer tokens, API keys (sk-*), passwords, Slack tokens. Applied before any output reaches LLM context or logs. |
| 2026-02-19 | Memory architecture: Merged NEXUS hybrid backends + ZeroClaw SQLite into 3-tier (hot/warm/cold) Python + FTS5 Rust | Best of both: NEXUS decay/tag logic + ZeroClaw FTS5 performance |
| 2026-02-19 | Orchestration strategy: Kept NEXUS HiveMind 7-phase but decomposed OrchestratorV7 into Mediator | Audit NX-CG recommended decomposition; Mediator pattern is testable |
| 2026-02-19 | Tool execution contract: Merged ZeroClaw Tool trait + NEXUS MCP client/server into unified MCP pipeline | MCP is the ecosystem standard; ZeroClaw traits provide the execution layer, NEXUS provides the client |
| 2026-02-25 | Fix model="default" hardcode — use provider.name() | Expert audit: "default" was sent to real LLM providers who don't understand it. Use `getattr(provider, '_model', None) or provider.name()` for correct model resolution. |
| 2026-02-25 | Fix ModelSelector fallback to gpt-5.2-codex | Stale fallback "claude-3-5-sonnet-20241022" referenced a model no longer default. All complexity levels already map to codex. |
| 2026-02-25 | Brain as MCP server deferred (Brain is client only) | Expert recommendation + VISION-ANALYSIS convergence: Brain should also serve tools to external callers. Deferred to post-0.2 as P2 priority. |
| 2026-02-25 | Evidence crypto-signing deferred (EU AI Act Aug 2026) | Evidence Packs need tamper-proof signatures for regulatory compliance. Timeline: before Aug 2026 EU AI Act deadline. |
| 2026-02-25 | Guard v2: regex → classifier (arXiv:2505.03574) | Current regex guard has known gaps (unicode homoglyphs, base64 bypass). LlamaFirewall-style classifier recommended for production. |
| 2026-02-25 | Evaluate Wassette before custom WASM runtime | Microsoft Wassette uses same Brain↔Core + WASM architecture. Evaluate before building custom wasmtime integration. |
| 2026-02-25 | v0.3.0: Evidence crypto with pynacl ed25519 | SHA-256 hash chain + ed25519 signing + RFC 6962 Merkle tree. pynacl chosen for ed25519 (mature, audited, no C compilation issues). Signing opt-in, hash chain automatic. EU AI Act Art. 12 compliance. |
| 2026-02-25 | v0.3.0: GuardBackend ABC + scoring | Introduced abstract base to allow composable guards (regex, tool invocation, ML classifier). Score 0-100 added alongside bool allowed for gradual enforcement. InputGuard aliased to RegexGuard for backward compat. |
| 2026-02-25 | v0.3.0: Red/Blue as EU AI Act Art. 9 evidence | Two modes: sync (10 template attacks) for fast CI, async (LLM-generated adversarial prompts) for thorough testing. Results written to EvidencePack for regulatory audit. |
| 2026-02-25 | v0.3.0: Brain MCP server — stdio only for v1 | 5 tools exposed (orchestrate, guard_check, evidence_export, swarm_execute, memory_recall). HTTP deferred to Core gateway proxy. Brain now bidirectional: client + server. |
| 2026-02-25 | v0.3.0: MCP handle_jsonrpc() refactor for HTTP reuse | Extracted reusable Value→Value handler from stdio loop. Both stdio and POST /mcp use same handler. SSE streaming deferred. |
| 2026-02-25 | v0.3.0: A2A subset implementation | Agent Card at /.well-known/agent.json + SendMessage/GetTask/ListTasks. Minimal viable A2A for agent discovery and interop. Full spec deferred. |
| 2026-02-26 | v0.4.0: Bottom-up approach (embeddings→registry→guard→dashboard) | Infrastructure first enables higher layers. Embeddings needed by both memory and guard. |
| 2026-02-26 | EmbeddingService: dual backend (sentence-transformers + Ollama) | sentence-transformers for offline/air-gapped, Ollama for users already running it. ABC makes both pluggable. |
| 2026-02-26 | ML Guard: ONNX + Ollama, stub for CI | ONNX for fast local inference (5-15ms), Ollama for simpler setup. Stub mode allows CI without model downloads. |
| 2026-02-26 | ygn-dash: Tauri 2 + React (same stack as opcode) | Reuse Yann's opcode expertise. Read-only consumer of ygn-core data. |
| 2026-02-26 | SqliteRegistry: eventual consistency via merge_nodes() | No Raft/etcd. Last-writer-wins on last_seen. Acceptable for discovery, not authorization. |
| 2026-02-26 | v0.5.0: Guard model download as separate CLI | PromptGuard-86M (~330MB) not bundled. Explicit `ygn-brain-guard-download` CLI avoids bloating pip install. Model cached in `~/.ygn/models/`. |
| 2026-02-26 | v0.5.0: EntityExtractor ABC for Temporal KG | Decoupled extraction from storage. RegexEntityExtractor for regex-based entity recognition. StubEntityExtractor for tests. Future: LLM-based extraction. |
| 2026-02-26 | v0.5.0: SqliteTaskStore replaces in-memory A2A task store | In-memory task store lost tasks between requests. SQLite with WAL mode provides persistence. Same pattern as SqliteRegistry. |
| 2026-02-26 | v0.5.0: Dashboard wired to live API, not mock data | All 5 dashboard pages now fetch from ygn-core gateway. Auto-refresh every 10s. Connection indicator in sidebar. |
| 2026-02-26 | v0.5.0: 14 TDD tasks across 2 parallel tracks | Track A (Python/Brain hardening) + Track B (Rust/Dashboard wiring). TDD mandatory throughout. E2E golden path as integration gate. |
| 2026-02-26 | v0.6.0: Generic Refinement Harness (Option 1 from analyse.md) | Most extensible approach. Poetiq is a preset, not the architecture. Supports future GEPA/DSPy policies. |
| 2026-02-26 | ConsensusSelector with +0.15 bonus for multi-provider agreement | Inspired by Poetiq's finding that ensemble multi-model improves results. Simple heuristic, not embedding-based. |
| 2026-02-26 | HarnessMemoryStore uses COLD tier for pattern capitalization | Poetiq's "learns how tasks are solved" — winning patterns stored for semantic recall in future runs. |
| 2026-02-26 | Fix README v0.2.1 + MCP 0.3.0 drifts in same release | analyse.md flagged these drifts — cleaning them up alongside the feature release. |
| 2026-02-26 | v0.7.0: Codex default model gpt-5.2-codex → gpt-5.3-codex | Codex CLI updated to gpt-5.3-codex as default. ModelSelector fallback updated accordingly. |
| 2026-02-26 | v0.7.0: Wire persistence — GuardLog SQLite + sessions from real JSONL | GET /guard/log now reads from ~/.ygn/guard_log.db (SQLite, read-only). GET /sessions scans ~/.ygn/evidence/ for real JSONL files. Eliminates mock/stub data in production endpoints. |
| 2026-02-26 | v0.7.0: MCP alignment — -32600 + Accept header | Added INVALID_REQUEST (-32600) error code per JSON-RPC 2.0 spec. Accept header awareness in MCP HTTP handler for content negotiation. |

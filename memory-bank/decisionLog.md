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

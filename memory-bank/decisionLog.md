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

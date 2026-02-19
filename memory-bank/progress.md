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

## Next

- [ ] M6/E6: IoA / Distributed swarm (registry, discovery, 2-node cooperation)
- [ ] M6/E7: Embodiment / Hardware simulator
- [ ] M7/E8: Self-healing + self-evolution (gated)
- [ ] M8/E9: Release ready (installer, quickstart, smoke tests)

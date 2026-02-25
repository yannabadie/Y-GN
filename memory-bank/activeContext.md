# Active Context

## Current Focus

- [2026-02-25] v0.3.0 release: Compliance, Security, Interoperability
- EU AI Act Art. 12 (evidence crypto) + Art. 9 (adversarial testing) compliance
- Brain↔Core MCP bidirectional: Brain is now both client AND server
- A2A protocol support for agent interoperability

## Completed Today (2026-02-25)

### v0.3.0 — 7 phases implemented
- A1: Evidence Pack Crypto — hash chain + ed25519 signing + Merkle tree
- A3: Guard v2 — GuardBackend ABC, scoring, ToolInvocationGuard, ClassifierGuard stub
- B3: Red/Blue Executor — template attacks (sync) + LLM adversarial (async)
- B1: Brain MCP Server — 5 tools over stdio JSON-RPC 2.0
- A2: Wassette Sandbox — policy mapping, availability check, fallback
- A4: MCP Streamable HTTP — handle_jsonrpc() refactor, POST /mcp route
- B2: A2A Agent Cards — /.well-known/agent.json + POST /a2a

## Test Counts (2026-02-25)

- Rust: 344 tests (336 + 8 new from wassette/a2a/gateway)
- Python: 336 tests (313 + 23 new from evidence/guard/swarm/mcp_server)
- Total: 680

## Known Gaps (Documented)

- Guard regex bypassed by unicode homoglyphs and base64 encoding (ClassifierGuard stub ready for ML-based)
- Wassette: integration ready but binary not yet available on Windows
- A2A: TaskStore is in-memory per-request (not shared across requests in gateway)
- Landlock: types exist, apply_linux() is explicit stub
- Distributed registry: in-memory HashMap, lost on restart
- Temporal KG: ColdEntry.relations declared, never populated

## Current Blockers

- HiveMind full pipeline with Gemini CLI times out on 3rd LLM call (use phase_timeout)
- Real LLM calls require CLI tools installed (codex, gemini)
- credential_vault::tests::drop_zeros test crashes on Windows (pre-existing unsafe issue)

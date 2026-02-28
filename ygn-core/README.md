# ygn-core

Rust data-plane for Y-GN — tool execution, channels, sandboxing, memory, and HTTP gateway.

## Build

```bash
cargo build -p ygn-core
cargo build --release -p ygn-core
```

## Quality Gates

```bash
cargo fmt --check
cargo clippy -- -D warnings
cargo test
```

## CLI Commands

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

## HTTP Gateway Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/health` | GET | Service health check |
| `/providers` | GET | List all configured LLM providers with capabilities |
| `/health/providers` | GET | Health status of all providers (circuit breaker state) |
| `/mcp` | POST | MCP over HTTP (JSON-RPC 2.0, Streamable HTTP transport) |
| `/.well-known/agent.json` | GET | A2A Agent Card discovery |
| `/a2a` | POST | A2A message handler (SendMessage, GetTask, ListTasks) |
| `/guard/log` | GET | Paginated guard decision log |
| `/sessions` | GET | Evidence Pack sessions list |
| `/memory/stats` | GET | Memory tier distribution |
| `/registry/nodes` | GET | List registered nodes |
| `/registry/sync` | POST | Cross-node registry sync |

## Works Today (E2E verified)

- MCP server over stdio (JSON-RPC 2.0): `initialize`, `tools/list`, `tools/call`
- Built-in tools: `echo`, `hardware` (simulated)
- Multi-provider LLM traits: Claude, OpenAI, Gemini, Ollama
- Credential vault with zero-on-drop API key management
- Token-bucket rate limiter per provider
- Circuit-breaker health tracking (5 consecutive failures)
- Process sandbox: 4 profiles (NoNet, Net, ReadOnlyFs, ScratchFs)
- Policy engine: Allow/Deny/RequireApproval with JSONL audit log
- SQLite FTS5 memory with BM25 ranking
- Channel trait: CLI, Telegram, Discord, Matrix adapters
- Skills system with topological-sort execution
- Node registry with capability-based discovery
- OpenTelemetry instrumentation

## Known Stubs

- **WASM/WASI**: Process-level policy checks only. No wasmtime dependency, no actual module execution.
- **Landlock**: Types declared, `apply_linux()` is an explicit stub.
- **Distributed registry**: In-memory HashMap, lost on restart.
- **Tunnel management**: cloudflared/tailscale/ngrok lifecycle types exist but depend on external binaries.

## Test Count

380 tests (unit + integration).

## License

Apache-2.0

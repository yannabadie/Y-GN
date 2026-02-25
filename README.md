# Y-GN (Yggdrasil-Grid Nexus)

**v0.2.1** — A distributed multi-agent runtime that separates reasoning from execution.

## Architecture

```
                        +---------------------------+
                        |        User / CLI         |
                        +------------+--------------+
                                     |
                   +-----------------+-----------------+
                   |                                   |
          +--------v--------+               +----------v---------+
          |   ygn-brain     |    MCP        |     ygn-core       |
          |   (Python)      | <-----------> |     (Rust)         |
          |                 |   JSON-RPC    |                    |
          | - Orchestrator  |   over stdio  | - Tool registry    |
          | - HiveMind 7ph  |               | - Process sandbox  |
          | - Swarm engine  |               | - Channels         |
          | - Evidence Pack |               | - Memory (SQLite)  |
          | - Guards        |               | - Gateway (Axum)   |
          +-----------------+               | - Node registry    |
                                            +--------------------+
```

**Brain** (Python) handles planning, multi-agent orchestration, and governance.
**Core** (Rust) handles tool execution, sandboxing, channels, and persistence.
They communicate over the **Model Context Protocol (MCP)**.

## Works Today (E2E verified 2026-02-25)

- **MCP Brain-Core integration** -- JSON-RPC 2.0 over stdio, echo tool discovery + invocation
- **Codex + Gemini CLI providers** -- real LLM inference via subprocess, no API cost
- **HiveMind 7-phase pipeline** -- diagnosis, analysis, planning, execution, validation, synthesis, completion (sync: deterministic; async: 4/7 phases LLM-backed)
- **Guard pipeline** -- regex-based prompt injection detection (3 attack categories: instruction override, role manipulation, delimiter injection)
- **Evidence Packs** -- auditable JSONL trace (session-stamped, per-entry timestamp/phase/kind/data)
- **Swarm engine** -- Parallel, Sequential, Specialist modes with async LLM execution
- **3-tier memory** -- Hot (TTL cache) / Warm (tag-indexed) / Cold (relation-linked) with word-overlap search
- **Process sandbox** -- 4 profiles (NoNet, Net, ReadOnlyFs, ScratchFs), path traversal prevention
- **Policy engine** -- risk assessment + action decision (Allow/Deny/RequireApproval) with audit trail
- **HTTP gateway** -- Axum with `/health`, `/providers`, `/health/providers`
- **SQLite FTS5 memory** -- BM25 ranking, WAL mode, trigger-synced index
- **CLI tools** -- `status`, `gateway`, `config schema`, `tools list`, `providers list`, `mcp`, `registry list`, `diagnose`

## Roadmap / Known Stubs

These features have types/interfaces but are not fully implemented:

| Feature | Current State | What's Missing |
|---------|--------------|----------------|
| WASM/WASI sandbox | Process-level policy checks only | No wasmtime runtime, no actual WASM module execution |
| Landlock OS sandbox | Types + `apply_linux()` stub | Explicit stub comment, not enforced |
| Distributed registry | In-memory HashMap | Lost on restart, no persistent backing store |
| Temporal Knowledge Graph | `ColdEntry.relations` declared | Never populated, no graph traversal |
| Swarm Red/Blue, PingPong, LeadSupport | Enum values exist | No executor implementations, fall back to sequential |
| A2A protocol | Not implemented | Referenced in roadmap only |
| Brain as MCP server | Brain is MCP client only | Cannot serve tools to external callers |
| Vector embeddings | Not implemented | Memory uses word-overlap matching |

## Quick Install

```bash
git clone https://github.com/yannabadie/Y-GN.git
cd Y-GN

# Build the Rust data-plane
cd ygn-core && cargo build --release && cd ..

# Install the Python control-plane
cd ygn-brain && pip install -e .[dev] && cd ..

# Verify
ygn-core status
python -c "from ygn_brain import Orchestrator; print('Brain OK')"
```

For detailed instructions (prerequisites, virtual environments, troubleshooting),
see **[INSTALL.md](INSTALL.md)**.

## Quick Demo

```bash
# Explore CLI tools
ygn-core tools list
ygn-core config schema

# Run a Brain pipeline (sync — deterministic, no LLM needed)
python -c "
from ygn_brain import Orchestrator
result = Orchestrator().run('What is 2+2?')
print(result['result'])
"

# Run with real LLM (requires Codex CLI installed)
YGN_LLM_PROVIDER=codex python -c "
import asyncio
from ygn_brain import Orchestrator
result = asyncio.run(Orchestrator().run_async('What is the capital of France?'))
print(result['result'][:200])
"

# Run all quality gates
make test
```

See the [`examples/`](examples/) directory for complete runnable demos.

## Project Structure

```
Y-GN/
  ygn-core/          Rust workspace -- data-plane binary
    src/               main.rs, mcp.rs, tool.rs, sandbox.rs, ...
    Cargo.toml
  ygn-brain/         Python package -- control-plane
    src/ygn_brain/     orchestrator.py, hivemind.py, mcp_client.py, ...
    pyproject.toml
  examples/          Runnable demo scripts (shell + Python)
  Makefile           Quality gates: make test / make lint / make fmt
  INSTALL.md         Installation & quickstart guide
  ROADMAP.md         Full project roadmap with milestones and epics
  CONTRIBUTING.md    Development workflow and conventions
  AGENTS.md          Agent team roles for multi-agent development
  LICENSE            Apache-2.0
```

## Test Counts (2026-02-25)

| Component | Tests |
|-----------|-------|
| ygn-core (Rust) | 336 |
| ygn-brain (Python) | 299+ |
| **Total** | **635+** |

## License

Y-GN is licensed under the [Apache License 2.0](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, workflow, quality
gates, and commit conventions.

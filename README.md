# Y-GN (Yggdrasil-Grid Nexus)

**v0.7.0** — A distributed multi-agent runtime that separates reasoning from execution.

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

## Works Today (E2E verified)

| Feature | File/Symbol | Verify Command |
|---------|------------|----------------|
| MCP Brain↔Core | `ygn-core/src/mcp.rs` | `cargo test mcp` |
| CLI providers (Codex+Gemini) | `codex_provider.py`, `gemini_provider.py` | `pytest tests/test_codex_provider.py -v` |
| Evidence Pack (hash chain + ed25519 + Merkle) | `evidence.py` | `pytest tests/test_evidence.py -v` |
| Guard pipeline (regex + ML option) | `guard.py`, `guard_ml.py` | `pytest tests/test_guard.py -v` |
| Persistent registry (SQLite) | `sqlite_registry.rs` | `cargo test sqlite_registry` |
| Memory (3-tier + embeddings + Temporal KG) | `tiered_memory.py` | `pytest tests/test_temporal_kg.py -v` |
| Brain MCP server (7 tools) | `mcp_server.py` | `pytest tests/test_mcp_server.py -v` |
| Refinement Harness (Poetiq-inspired) | `harness/engine.py` | `pytest tests/test_harness_engine.py -v` |
| Governance Dashboard (Tauri) | `ygn-dash/` | `cd ygn-dash && bun run build` |

## Planned / Partially Wired

| Feature | Status | Blocker |
|---------|--------|---------|
| WASM/WASI sandbox | Stub (Wassette ready) | Wassette binary not on Windows |
| Landlock OS sandbox | Stub (types exist) | Linux-only |
| Real ML guard model | Code ready, model not bundled | Run `ygn-brain-guard-download` |
| Gateway shared state | Per-request `:memory:` | Axum State wiring pending |

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

## Test Counts (2026-02-26)

| Component | Tests |
|-----------|-------|
| ygn-core (Rust) | 373 |
| ygn-brain (Python) | 442 |
| **Total** | **815** |

## License

Y-GN is licensed under the [Apache License 2.0](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, workflow, quality
gates, and commit conventions.

# Y-GN (Yggdrasil-Grid Nexus)

**v0.7.0** -- A distributed multi-agent runtime that separates reasoning from execution.

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
          | - Context       |               | - Node registry    |
          |   Compiler      |               +--------------------+
          | - Tool          |
          |   Interrupts    |
          +-----------------+

Context Compilation Layer (inside ygn-brain):

  Session(EventLog)
        |
        v
  +-----------+     +----------+     +----------------+     +-----------------+
  | History   | --> | Compactor| --> | Memory         | --> | Artifact        |
  | Selector  |     |          |     | Preloader      |     | Attacher        |
  +-----------+     +----------+     +----------------+     +-----------------+
        |                                                          |
        v                                                          v
  TokenBudget                                              ArtifactStore
  (budget-aware)                                   (SqliteArtifactStore / FsArtifactStore)
        |
        v
  WorkingContext  -->  LLM call
```

**Brain** (Python) handles planning, multi-agent orchestration, context compilation, and governance.
**Core** (Rust) handles tool execution, sandboxing, channels, and persistence.
They communicate over the **Model Context Protocol (MCP)**.

## Works Today (E2E verified)

| Feature | File/Symbol | Verify Command |
|---------|------------|----------------|
| MCP Brain-Core | `ygn-core/src/mcp.rs` | `cargo test mcp` |
| CLI providers (Codex+Gemini) | `codex_provider.py`, `gemini_provider.py` | `pytest tests/test_codex_provider.py -v` |
| Evidence Pack (hash chain + ed25519 + Merkle) | `evidence.py` | `pytest tests/test_evidence.py -v` |
| Guard pipeline (regex + ML option) | `guard.py`, `guard_ml.py` | `pytest tests/test_guard.py -v` |
| Persistent registry (SQLite) | `sqlite_registry.rs` | `cargo test sqlite_registry` |
| Memory (3-tier + embeddings + Temporal KG) | `tiered_memory.py` | `pytest tests/test_temporal_kg.py -v` |
| Brain MCP server (8 tools) | `mcp_server.py` | `pytest tests/test_mcp_server.py -v` |
| Refinement Harness (Poetiq-inspired) | `harness/engine.py` | `pytest tests/test_harness_engine.py -v` |
| Context Compiler | `context_compiler/` | `pytest tests/test_context_compiler_e2e.py -v` |
| Tool Interrupts | `tool_interrupt/` | `pytest tests/test_tool_interrupt.py -v` |
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

# Run a Brain pipeline (sync -- deterministic, no LLM needed)
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

# Run the context compiler demo
python -m ygn_brain.demo_compiler

# Run all quality gates
make test
```

See the [`examples/`](examples/) directory for complete runnable demos.

## CLI Commands

### ygn-core

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

### ygn-brain

```bash
ygn-brain-mcp                  # Start Brain MCP server over stdio
ygn-brain-repl                 # Interactive REPL
ygn-brain-guard-download       # Download PromptGuard-86M model
ygn-brain-demo-compiler        # Demo: context compiler with artifact externalization
```

### Brain MCP Server Tools

The Brain MCP server (`ygn-brain-mcp`) exposes 8 tools:

1. `orchestrate` -- run the orchestrator pipeline
2. `guard_check` -- validate input against guard pipeline
3. `evidence_export` -- export Evidence Pack as JSONL
4. `swarm_execute` -- run a swarm executor (Parallel, Sequential, RedBlue, etc.)
5. `memory_recall` -- recall from 3-tier memory by key
6. `memory_search_semantic` -- semantic vector search over memory
7. `orchestrate_refined` -- orchestrate with refinement harness
8. `orchestrate_compiled` -- context-compiled orchestration with token budget

## Project Structure

```
Y-GN/
  ygn-core/          Rust workspace -- data-plane binary
    src/               main.rs, mcp.rs, tool.rs, sandbox.rs, ...
    Cargo.toml
  ygn-brain/         Python package -- control-plane
    src/ygn_brain/     orchestrator.py, hivemind.py, mcp_client.py, ...
      context_compiler/  session.py, processors.py, working_context.py,
                         artifact_store.py, token_budget.py
      tool_interrupt/    events.py, handler.py, normalizer.py, schemas.py
      harness/           engine.py, generator.py, verifier.py, ...
    pyproject.toml
  ygn-dash/          Tauri 2 + React 18 governance dashboard
    src/pages/         Dashboard, EvidenceViewer, GuardLog,
                       MemoryExplorer, NodeRegistry
  examples/          Runnable demo scripts (shell + Python)
  docs/              Technical documentation and plans
  memory-bank/       Persistent project context across sessions
  Makefile           Quality gates: make test / make lint / make fmt
  INSTALL.md         Installation & quickstart guide
  ROADMAP.md         Full project roadmap with milestones and epics
  CONTRIBUTING.md    Development workflow and conventions
  AGENTS.md          Agent team roles for multi-agent development
  LICENSE            Apache-2.0
```

## Test Counts (2026-02-28)

| Component | Tests |
|-----------|-------|
| ygn-core (Rust) | 380 |
| ygn-brain (Python) | 475 |
| **Total** | **855** |

## License

Y-GN is licensed under the [Apache License 2.0](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, workflow, quality
gates, and commit conventions.

# Y-GN (Yggdrasil-Grid Nexus)

A distributed multi-agent runtime that separates reasoning from execution,
enabling secure and observable AI agent deployments from edge to cloud.

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
          | - HiveMind 7ph  |               | - Sandbox (WASM)   |
          | - Swarm engine  |               | - Channels         |
          | - Evidence Pack |               | - Memory (SQLite)  |
          | - Guards        |               | - Gateway (Axum)   |
          +-----------------+               | - Node registry    |
                                            +--------------------+
```

**Brain** (Python) handles planning, multi-agent orchestration, and governance.
**Core** (Rust) handles tool execution, sandboxing, channels, and persistence.
They communicate over the **Model Context Protocol (MCP)**.

## Key Features

- **7-phase HiveMind pipeline** -- diagnosis, analysis, planning, execution, validation, synthesis, completion
- **Hybrid swarm engine** -- parallel, sequential, red/blue, ping-pong, lead-support, and specialist modes
- **Evidence Packs** -- auditable trace of every decision, tool call, and output
- **MCP integration** -- Brain discovers and calls Core tools via JSON-RPC 2.0
- **WASM/WASI sandbox** -- execute untrusted tools with configurable security policies
- **Tiered memory** -- hot/warm/cold storage with temporal knowledge graph
- **Distributed agents** -- node registry, teaming, and IoA-style collaboration
- **OpenTelemetry** -- traces and metrics across both Brain and Core

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

# Run a Brain pipeline
python -c "
from ygn_brain import Orchestrator
result = Orchestrator().run('Summarize WASM sandbox security')
print(result['result'])
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

## Milestones

| ID | Name | Status |
|----|------|--------|
| M0 | Bootstrap -- monorepo, CI, agent team | Complete |
| M1 | Core usable -- config, gateway, CLI | Complete |
| M2 | Brain usable -- HiveMind pipeline, Evidence Pack | Complete |
| M3 | Brain-Core integration -- MCP tool calls | Complete |
| M4 | Secure tool execution -- WASM sandbox, policies | Complete |
| M5 | Memory v1 -- tiered storage, temporal KG | Complete |
| M6 | Distributed swarm -- registry, teaming, IoA | Complete |
| M7 | Self-healing -- auto-diagnosis, scaffold evolution | Complete |
| M8 | Release ready -- installer, docs, examples | Complete |

## Release v0.1.0

First MVP release (2026-02-24). Both ygn-core and ygn-brain are independently
usable and integrate over MCP. See [CHANGELOG.md](CHANGELOG.md) for full details.

**Quick verification:**

```bash
# 1. Build & install (see INSTALL.md for details)
cd ygn-core && cargo build --release && cd ..
cd ygn-brain && pip install -e .[dev] && cd ..

# 2. Run all quality gates
make test

# 3. E2E demo: Brain calls Core tool via MCP
python examples/03_mcp_integration.py
```

**Test counts:** 336 Rust + 245 Python = 581 tests.

## License

Y-GN is licensed under the [Apache License 2.0](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, workflow, quality
gates, and commit conventions.

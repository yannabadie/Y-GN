# Y-GN Installation & Quickstart Guide

This guide walks you through installing Y-GN (Yggdrasil-Grid Nexus) from source
and running your first commands. Target time: under 10 minutes.

---

## 1. Prerequisites

| Dependency | Minimum Version | How to Install |
|------------|----------------|----------------|
| **Git** | any recent | [git-scm.com](https://git-scm.com/) or your OS package manager |
| **Rust toolchain** | 1.70+ | See below |
| **Python** | 3.11+ | [python.org](https://www.python.org/downloads/) or your OS package manager |

### Install Rust (if not already installed)

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

Follow the on-screen prompts (the defaults work fine), then reload your shell:

```bash
source "$HOME/.cargo/env"
```

Verify:

```bash
rustc --version   # should print 1.70.0 or higher
cargo --version
```

### Install Python 3.11+

**macOS (Homebrew):**
```bash
brew install python@3.11
```

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install python3.11 python3.11-venv python3-pip
```

**Windows:**
Download and run the installer from [python.org](https://www.python.org/downloads/).
Make sure "Add Python to PATH" is checked.

Verify:

```bash
python3 --version   # should print 3.11.x or higher
```

> **Tip:** On Windows, the command may be `python` rather than `python3`.

---

## 2. Clone the Repository

```bash
git clone https://github.com/yannabadie/Y-GN.git
cd Y-GN
```

You should see the following top-level structure:

```
Y-GN/
  ygn-core/      # Rust data-plane (tools, channels, sandbox, memory)
  ygn-brain/     # Python control-plane (orchestration, swarm, evidence)
  Makefile        # Quality gates
  examples/       # Example scripts
  INSTALL.md      # This file
```

---

## 3. Build ygn-core (Rust)

```bash
cd ygn-core
cargo build --release
```

This compiles the `ygn-core` binary into `ygn-core/target/release/ygn-core`.

To make it available on your PATH for the rest of this guide, either:

```bash
# Option A: add the release directory to PATH (current session)
export PATH="$PWD/target/release:$PATH"

# Option B: copy the binary somewhere already on PATH
cp target/release/ygn-core ~/.cargo/bin/
```

Return to the project root:

```bash
cd ..
```

---

## 4. Install ygn-brain (Python)

It is recommended to use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
```

Then install the package in editable mode with dev dependencies:

```bash
cd ygn-brain
pip install -e .[dev]
```

Return to the project root:

```bash
cd ..
```

---

## 5. Verify Installation

Run these commands from the project root to confirm everything is working:

```bash
# Rust binary
ygn-core status
ygn-core tools list

# Python package
python -c "from ygn_brain import Orchestrator; print('Brain OK')"
```

Expected output:

- `ygn-core status` prints the node identity and status information.
- `ygn-core tools list` prints the registered tools (at minimum, `echo`).
- The Python one-liner prints `Brain OK`.

---

## 6. Run the Quality Gates

The Makefile at the project root runs all linters and tests for both Rust and Python:

```bash
make test
```

This executes:

1. **Lint** -- `cargo fmt --check`, `cargo clippy`, `ruff check`, `mypy`
2. **Test (Rust)** -- `cargo test`
3. **Test (Python)** -- `pytest -q`

If everything passes, you will see: `All gates passed.`

---

## 7. Quickstart Scenarios

Below are three scenarios that demonstrate the key capabilities of Y-GN.
Complete example scripts are available in the `examples/` directory.

### Scenario A: CLI Tool Execution

Explore the Core runtime from your terminal:

```bash
# Check node status
ygn-core status

# Export the configuration JSON schema
ygn-core config schema

# List all registered tools
ygn-core tools list

# Show this node's registry info
ygn-core registry self-info
```

See: [`examples/01_cli_tools.sh`](examples/01_cli_tools.sh)

### Scenario B: Brain Orchestration (HiveMind Pipeline)

Run a query through the Brain's 7-phase HiveMind pipeline using the Python REPL:

```python
from ygn_brain import Orchestrator

orch = Orchestrator()
result = orch.run("What are the security implications of running untrusted WASM modules?")

print("Result:", result["result"])
print("Session:", result["session_id"])
```

The Orchestrator drives the full pipeline: guard check, diagnosis, analysis,
planning, execution, validation, and synthesis. Each step is recorded in an
Evidence Pack for auditability.

See: [`examples/02_brain_pipeline.py`](examples/02_brain_pipeline.py)

### Scenario C: Brain-to-Core Integration via MCP

The Brain communicates with the Core over the Model Context Protocol (MCP), a
JSON-RPC 2.0 protocol transported over stdio. This lets the Brain discover and
call tools that the Core exposes.

```python
import asyncio
from ygn_brain import McpClient

async def main():
    async with McpClient() as client:
        # Discover tools
        tools = await client.list_tools()
        print("Available tools:", [t["name"] for t in tools])

        # Call the echo tool
        reply = await client.call_tool("echo", {"text": "Hello from Brain!"})
        print("Echo reply:", reply)

asyncio.run(main())
```

> **Note:** This requires `ygn-core` to be on your PATH so that the McpClient
> can spawn `ygn-core mcp` as a subprocess.

See: [`examples/03_mcp_integration.py`](examples/03_mcp_integration.py)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `cargo build` fails with missing dependencies | Run `rustup update` and ensure your Rust version is 1.70+ |
| `pip install -e .[dev]` fails | Make sure you are using Python 3.11+ and have activated a venv |
| `ygn-core: command not found` | Add `ygn-core/target/release` to your PATH (see step 3) |
| `make test` fails on lint | Run `make fmt` to auto-format, then retry |
| MCP integration hangs | Verify `ygn-core mcp` runs standalone (`echo '{}' | ygn-core mcp`) |

---

## Next Steps

- Read the [ROADMAP.md](ROADMAP.md) for the full project plan and milestone details.
- See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and quality gates.
- Explore the `examples/` directory for runnable demo scripts.

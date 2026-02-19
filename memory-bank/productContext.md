# Product Context

## Overview

Y-GN (Yggdrasil-Grid Nexus) is a distributed multi-agent runtime that fuses:
- **NEXUS NX-CG** as the cognitive control-plane (FSM, HiveMind, HybridSwarm, Evidence Packs, governance)
- **ZeroClaw** as the data-plane of execution (Rust runtime, channels, tunnels, tools, sandbox, memory, hardware)

## Architecture

- **ygn-brain/** (Python) — planning, multi-agent orchestration, governance, scoring, Evidence Packs
- **ygn-core/** (Rust) — tool execution, channels, tunnels, WASM/WASI sandboxing, memory engine, hardware
- Integration via **MCP** (Model Context Protocol) for tool discovery + invocation

## Core Features

- HiveMind 7-phase pipeline: Diagnosis → Analysis → Planning → Execution → Validation → Synthesis → Complete
- HybridSwarm with modes: Parallel, Sequential, RedBlue, PingPong, LeadSupport, Specialist
- Evidence Packs for auditable execution traces (JSONL)
- 3-tier memory: Hot (cache) / Warm (temporal index) / Cold (Temporal KG + embeddings)
- WASM/WASI sandbox for untrusted tool execution
- Multi-node IoA (Internet of Agents) distributed architecture

## Technical Stack

- Rust (ygn-core): Axum, Tokio, Serde, OpenTelemetry, Clap, wasmtime (planned)
- Python (ygn-brain): Pydantic, OpenTelemetry, pytest, ruff, mypy
- Protocols: MCP, HTTP, µACP (feature-flagged)
- License: Apache-2.0

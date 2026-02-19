# Project Brief

## Purpose

Build a distributed multi-agent runtime (Y-GN) that merges NEXUS NX-CG's cognitive orchestration with ZeroClaw's Rust execution engine, producing a secure, observable, and extensible platform for AI agent deployment across local, edge, and cloud environments.

## Target Users

- Developers building multi-agent AI systems
- Teams needing auditable, sandboxed tool execution for AI agents
- Edge/IoT deployments requiring lightweight agent runtimes

## MVP Scope

An agent usable via CLI + daemon, capable of:
1. Receiving a request (CLI or Telegram)
2. Planning via Brain (HiveMind pipeline)
3. Executing via Core (sandboxed tools)
4. Producing an Evidence Pack
5. Persisting memory across sessions

## Non-Goals (Initial)

- Full React UI (post-MVP)
- All channels supported at once (start with 1-2)

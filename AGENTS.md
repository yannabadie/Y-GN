# AGENTS.md -- Y-GN Agent Team

This file defines the agent team roles for Claude Code multi-agent development.

## Roles

| ID | Handle | Focus Areas |
|----|--------|-------------|
| RUST_CORE | @RustCoreLead | ygn-core, gateway, channels, runtime, config, release |
| PY_BRAIN | @PyBrainLead | ygn-brain, orchestration, swarm, evidence, governance |
| SEC | @SecurityLead | sandbox, policies, supply-chain, threat-model |
| MEMORY | @MemoryLead | sqlite/fts/vector, temporal KG, SwiftMem indexing, benchmarks |
| OBS | @ObservabilityLead | OpenTelemetry, metrics, profiling, dashboards |
| DOCS | @DocsReleaseLead | ROADMAP, DECISIONS, user docs, release checklist |

## Coordination Rules

- **1 worktree per epic** -- no concurrent edits on the same files across epics.
- **TDD mandatory** -- no business code without tests (`pytest` / `cargo test`).
- **Stop-the-line** if any quality gate fails.
- **Decision Log** -- every non-trivial decision goes to `memory-bank/decisionLog.md`.
- No cross-epic refactors unless agreed in Decision Log.

## Subagent Invocation

Each role maps to a Claude Code subagent. When spawning subagents:
- Provide the role ID and focus areas as context.
- Scope file access to the role's directories.
- Require all quality gates to pass before merging.

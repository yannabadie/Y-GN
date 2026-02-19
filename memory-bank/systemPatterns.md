# System Patterns

## Architectural Patterns

- **Brain/Core separation**: Reasoning (Python) vs Execution (Rust), connected via MCP protocol
- **Mediator orchestrator**: Lightweight orchestrator delegates to StateMachineHandler, TaskRouter, ContextBuilder, GuardPipeline, TaskExecutor (replaces OrchestratorV7 god-object)
- **Trait-based subsystems** (Rust): providers, channels, tools, memory, security, runtime — each behind a trait for testability and swappability
- **Evidence Pack**: Every execution produces an auditable JSONL trace with inputs, decisions, tool calls, sources, outputs, telemetry IDs

## Design Patterns

- **FSM-driven pipeline**: HiveMind 7-phase (Diagnosis → Analysis → Planning → Execution → Validation → Synthesis → Complete) with retry from Validation → Execution
- **Multi-wall security**: WASM/WASI sandbox → OS sandbox → allowlists/RBAC → runtime behavior analysis → approval gates
- **3-tier memory**: Hot (TTL cache) → Warm (temporal index + tags) → Cold (Temporal KG + embeddings)

## Common Idioms

- TDD: tests first, then implementation
- 1 worktree per epic, no cross-epic refactors
- Decision Log for every non-trivial choice
- Quality gates: fmt → lint → test → security scan

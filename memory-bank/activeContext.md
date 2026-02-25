# Active Context

## Current Focus

- [2026-02-25] Post-audit overhaul: fact-first docs, bug fixes, real E2E verification
- Version alignment: v0.2.1 across pyproject.toml, Cargo.toml, __init__.py, CHANGELOG
- 4 bug fixes applied: model hardcode, stale fallback, evidence kind constraint, phase timeout

## Completed Today (2026-02-25)

- Version alignment: 0.1.0 → 0.2.1 in pyproject.toml, Cargo.toml, __init__.py
- Fix: HiveMind/Swarm model="default" → provider.name() (5 locations)
- Fix: ModelSelector stale fallback "claude-3-5-sonnet-20241022" → "gpt-5.2-codex"
- Fix: EvidenceKind StrEnum constrains kind field (input/decision/tool_call/source/output/error)
- Fix: HiveMind phase_timeout with asyncio.wait_for + graceful fallback
- README fact-first rewrite: "Works Today" vs "Roadmap / Known Stubs"
- New ygn-core/README.md
- 14 new tests (3 hivemind, 1 router, 5 evidence, 5 guard)

## Test Counts (2026-02-25)

- Rust: 336 tests
- Python: 299+ tests (before new additions) + 14 new = 313+
- Total: 649+

## Known Bugs (Fixed 2026-02-25)

- [FIXED] model="default" hardcoded in HiveMind + Swarm async pipeline
- [FIXED] ModelSelector fallback referenced stale Claude model
- [FIXED] EvidenceEntry.kind unconstrained (any string accepted)
- [FIXED] HiveMind pipeline had no per-phase timeout

## Known Gaps (Documented)

- Guard regex bypassed by unicode homoglyphs and base64 encoding
- WASM/WASI: process-level policy checks only, no wasmtime runtime
- Landlock: types exist, apply_linux() is explicit stub
- Distributed registry: in-memory HashMap, lost on restart
- Temporal KG: ColdEntry.relations declared, never populated
- Swarm Red/Blue, PingPong, LeadSupport: enum values only
- Brain is MCP client only (cannot serve tools)

## Current Blockers

- HiveMind full pipeline with Gemini CLI times out on 3rd LLM call (use phase_timeout)
- Real LLM calls require CLI tools installed (codex, gemini)

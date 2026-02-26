# Active Context

## Current Focus

- [2026-02-26] v0.7.0 release: Hardening Sprint "Truth & Wiring"
- README fact-first rewrite, wire persistence (GuardLog, sessions), MCP alignment, Codex model update

## Test Counts (2026-02-26)

- Rust: 380 tests
- Python: 445 tests
- Total: 825

## Known Gaps (Documented)

- Guard regex bypassed by unicode homoglyphs and base64 encoding (OnnxClassifierGuard now available for ML-based detection)
- Wassette: integration ready but binary not yet available on Windows
- Landlock: types exist, apply_linux() is explicit stub
- OnnxClassifierGuard requires model download via `ygn-brain-guard-download` (not bundled)

## Resolved in v0.5.0

- A2A TaskStore now persistent (SqliteTaskStore replaces in-memory)
- Distributed registry now persistent (SqliteRegistry since v0.4.0)
- Temporal KG ColdEntry.relations now populated via EntityExtractor + relation index
- Dashboard connected to live API data (was mock data)

## Current Blockers

- HiveMind full pipeline with Gemini CLI times out on 3rd LLM call (use phase_timeout)
- Real LLM calls require CLI tools installed (codex, gemini)
- credential_vault::tests::drop_zeros test crashes on Windows (pre-existing unsafe issue)

# Active Context

## Current Focus

- [2026-02-26] v0.6.0 release: Refinement Harness (Poetiq-inspired)
- Generic generate-verify-refine loop, multi-provider consensus, pattern capitalization, orchestrate_refined MCP tool

## Test Counts (2026-02-26)

- Rust: 373 tests
- Python: 442 tests
- Total: 815

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

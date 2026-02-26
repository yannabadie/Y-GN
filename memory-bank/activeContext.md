# Active Context

## Current Focus

- [2026-02-26] v0.4.0 release: Observable Governance
- Vector embeddings (sentence-transformers + Ollama), persistent registry, ML guard, Tauri dashboard

## Test Counts (2026-02-26)

- Rust: 367 tests
- Python: 371 tests
- Total: 738

## Known Gaps (Documented)

- Guard regex bypassed by unicode homoglyphs and base64 encoding (ClassifierGuard stub ready for ML-based)
- Wassette: integration ready but binary not yet available on Windows
- A2A: TaskStore is in-memory per-request (not shared across requests in gateway)
- Landlock: types exist, apply_linux() is explicit stub
- Distributed registry: in-memory HashMap, lost on restart
- Temporal KG: ColdEntry.relations declared, never populated

## Current Blockers

- HiveMind full pipeline with Gemini CLI times out on 3rd LLM call (use phase_timeout)
- Real LLM calls require CLI tools installed (codex, gemini)
- credential_vault::tests::drop_zeros test crashes on Windows (pre-existing unsafe issue)

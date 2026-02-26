# Y-GN v0.5.0 — Production-Ready

**Date**: 2026-02-26
**Theme**: Make everything work end-to-end.
**Approach**: Parallel Tracks — Track A (Python/Brain) + Track B (Rust/Dashboard)
**Timeline**: 6+ weeks (comprehensive)
**LLM provider for E2E**: Codex CLI (CodexCliProvider)

---

## Strategic Context

v0.4.0 added embeddings, persistent registry, ML guard (stub), and a Tauri dashboard with mock data. v0.5.0 makes all of it production-grade: real ML inference, populated knowledge graph, reliable HiveMind pipeline, live dashboard, and an E2E demo proving the entire stack works.

---

## Track A — Python/Brain Production Hardening

### A1: Real ML Guard (Weeks 1-2)

**Goal**: Move OnnxClassifierGuard from stub to real ONNX inference with PromptGuard-86M.

**Model**: `meta-llama/Prompt-Guard-86M` (86M params, purpose-built for prompt injection).

**New CLI**: `ygn-brain-guard-download` — downloads from HF Hub, exports to ONNX via `optimum`, saves to `~/.ygn/models/prompt-guard-86m/`.

**Changes to `guard_ml.py`**:
- `OnnxClassifierGuard(stub=False, model_path="~/.ygn/models/prompt-guard-86m/")` → real inference
- Tokenize with `AutoTokenizer`, run `InferenceSession`, softmax, injection probability
- Threshold: score >= 50.0 → unsafe

**Benchmark**: Re-run 10 attack templates. Target 80%+ coverage (up from 50% regex-only).

**Config**: `YGN_GUARD_MODEL_DIR=~/.ygn/models/`

**Tests (3, @pytest.mark.slow)**: Real model loads, detects attack, coverage benchmark.

### A2: Temporal Knowledge Graph (Weeks 3-4)

**Goal**: Populate `ColdEntry.relations` and enable multi-hop reasoning.

**Entity extraction** (regex-based, no ML for v0.5.0):
- Extract: function/class names, URLs, file paths, error codes, API endpoints
- Patterns: `def \w+`, `class \w+`, `https?://\S+`, `/[\w/]+\.\w+`

**Knowledge graph** in `tiered_memory.py`:
- `_relation_index: dict[str, set[str]]` — entity → ColdEntry keys
- On COLD store: extract entities, populate `relations`, update index
- `recall_by_relation(entity: str) -> list[MemoryEntry]`

**Multi-hop** (HippoRAG-inspired):
- `recall_multihop(query, hops=2)` — BM25/semantic recall → follow relations → rank by relevance + connectivity

**Tests (6)**: Entity extraction, relation index, single-hop, multi-hop, empty relations, backward compat.

### A3: HiveMind Reliability (Weeks 5-6)

**Goal**: Fix timeouts, add retry, make 7-phase pipeline reliable with real LLMs.

**Fixes**:
1. Per-phase timeout with `asyncio.wait_for(timeout=phase_timeout)`
2. On timeout: skip phase, continue with degraded result
3. On provider error: retry once after 1s exponential backoff
4. `PhaseResult` dataclass: `{phase, status, output, latency_ms}`
5. Evidence Pack records phase status

**Codex CLI hardening** (`codex_provider.py`):
- `--timeout` flag on subprocess
- Robust JSONL parsing (partial lines, empty responses)
- `is_available()` pre-check

**Tests (5)**: Timeout degradation, retry, PhaseResult in evidence, empty response, full pipeline.

### A4: Entity Extraction Service (Weeks 5-6)

**Goal**: Modular entity extraction for Temporal KG.

**New file**: `ygn-brain/src/ygn_brain/entity_extraction.py`
- `EntityExtractor` ABC with `extract(text) -> list[str]`
- `RegexEntityExtractor` — pattern-based
- `StubEntityExtractor` — returns empty list
- Future: `LLMEntityExtractor`

**Tests (3)**: ABC contract, regex extraction, stub empty.

---

## Track B — Rust/Dashboard Production Wiring

### B1: Missing API Endpoints (Weeks 1-2)

**Goal**: Add all endpoints the dashboard needs.

**New routes in `gateway.rs`**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /guard/log` | GET | Paginated guard log from `~/.ygn/guard_log.jsonl` |
| `GET /guard/stats` | GET | Guard statistics (calls Brain MCP or reads local stats) |
| `GET /sessions` | GET | List Evidence Pack sessions from `~/.ygn/evidence/` |
| `GET /sessions/{id}` | GET | Export specific Evidence Pack |
| `GET /memory/stats` | GET | Memory tier distribution |

**Data sources**: Read Evidence Pack JSONL files and guard log from disk. No Brain dependency for read-only endpoints.

**Storage locations**:
- Evidence Packs: `~/.ygn/evidence/{session_id}.jsonl`
- Guard log: `~/.ygn/guard_log.jsonl`

**Tests (5)**: One per endpoint returning valid JSON.

### B2: Dashboard Wired to Live Data (Weeks 3-4)

**Goal**: Replace all mock data with real API calls.

**Per-page changes**:
- Dashboard: add `/guard/stats` fetch, real counts
- GuardLog: fetch `/guard/log` instead of mocks
- EvidenceViewer: fetch `/sessions` and `/sessions/{id}`
- NodeRegistry: already fetches `/registry/nodes` (shows data when gateway self-registers)
- MemoryExplorer: fetch `/memory/stats`

**Additional features**:
- Auto-refresh every 10s on Dashboard and GuardLog
- Connection status indicator in sidebar (green/red dot)
- Settings page: configure ygn-core URL (default `localhost:3000`)

**Tests (3)**: vitest component render tests.

### B3: A2A TaskStore Persistence (Weeks 3-4)

**Goal**: SQLite-backed TaskStore replacing in-memory per-request store.

**New in `a2a.rs`**:
- `SqliteTaskStore` backed by `~/.ygn/a2a_tasks.db`
- Schema: `tasks (id PK, status, message, result, created_at, updated_at)`
- Shared via Axum `State<Arc<SqliteTaskStore>>`
- Gateway self-registration on startup

**Tests (3)**: CRUD, persistence across requests, list tasks.

### B4: E2E Golden Path Demo (Weeks 5-6)

**Goal**: Single command proving the full stack works.

**Script**: `examples/golden_path.py`
1. Start ygn-core gateway (background)
2. Start ygn-brain MCP server (background)
3. Brain: HiveMind pipeline with Codex CLI
4. Brain: produce signed Evidence Pack
5. Core: verify hash chain + signature
6. Dashboard: session visible in EvidenceViewer
7. Print summary

**Integration test**: `tests/test_e2e_golden_path.py` (gated `@pytest.mark.e2e`, requires Codex CLI)

**Tests (2)**: E2E round-trip, evidence verification.

---

## New files summary

| File | Track | Description |
|------|-------|-------------|
| `ygn-brain/src/ygn_brain/entity_extraction.py` | A4 | EntityExtractor ABC + RegexEntityExtractor |
| `ygn-brain/scripts/guard_download.py` | A1 | Model download CLI |
| `examples/golden_path.py` | B4 | E2E demo script |
| `ygn-dash/src/pages/Settings.tsx` | B2 | Dashboard settings page |

## Modified files summary

| File | Track | Changes |
|------|-------|---------|
| `ygn-brain/src/ygn_brain/guard_ml.py` | A1 | Real ONNX inference |
| `ygn-brain/src/ygn_brain/tiered_memory.py` | A2 | Relation index, multi-hop recall |
| `ygn-brain/src/ygn_brain/hivemind.py` | A3 | Phase timeout, retry, PhaseResult |
| `ygn-brain/src/ygn_brain/codex_provider.py` | A3 | Timeout flag, robust parsing |
| `ygn-core/src/gateway.rs` | B1 | 5 new endpoints |
| `ygn-core/src/a2a.rs` | B3 | SqliteTaskStore |
| `ygn-dash/src/pages/*.tsx` | B2 | Replace mocks with API calls |
| `ygn-dash/src/App.tsx` | B2 | Add settings route, connection indicator |

---

## Test count estimate

| Track | Section | New tests |
|-------|---------|-----------|
| A | A1 Real ML Guard | 3 (slow) |
| A | A2 Temporal KG | 6 |
| A | A3 HiveMind reliability | 5 |
| A | A4 Entity extraction | 3 |
| B | B1 API endpoints | 5 |
| B | B2 Dashboard wiring | 3 (vitest) |
| B | B3 A2A persistence | 3 |
| B | B4 E2E demo | 2 (e2e) |
| **Total** | | **~30** |

Expected total: **738 + 30 = ~768 tests**

---

## Success criteria

1. PromptGuard-86M runs locally, detects 80%+ of attack templates
2. Temporal KG populates relations, multi-hop recall returns connected entries
3. HiveMind completes 7 phases with Codex CLI without hanging
4. Dashboard shows live data from running ygn-core
5. E2E golden path demo completes successfully
6. A2A tasks persist across gateway restarts
7. All tests pass, lint clean

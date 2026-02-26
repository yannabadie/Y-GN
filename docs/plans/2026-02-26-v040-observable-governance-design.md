# Y-GN v0.4.0 — Observable Governance

**Date**: 2026-02-26
**Theme**: Every agent decision is searchable, auditable, and visible.
**Direction**: Option A — Governance & Audit for LLM agents
**Timeline**: 6+ weeks (comprehensive)
**Audience**: Internal (Motherson Aerospace) + Open-source community + Enterprise prospects

---

## Strategic Context

v0.3.0 shipped compliance foundations (Evidence crypto, Guard v2, Red/Blue, A2A). v0.4.0 completes the governance story by adding:

1. **Semantic memory** — vector embeddings for meaningful recall
2. **Persistent registry** — nodes survive restarts, cross-node sync
3. **ML-based guard** — real classifier replacing regex-only detection
4. **Governance dashboard** — Tauri desktop app making it all visible

Approach: **Bottom-Up Foundation** — embeddings first (infrastructure), then registry (persistence), then ML guard (intelligence), then dashboard (presentation). Each phase builds on the previous.

---

## 1. Vector Embeddings (Weeks 1-2)

### Goal

Add semantic search to both Python memory and Rust memory using locally-hosted embedding models. Zero external API calls required.

### New file: `ygn-brain/src/ygn_brain/embeddings.py`

**`EmbeddingService` ABC**:
- `embed(texts: list[str]) -> list[list[float]]` — batch embedding
- `dimension() -> int` — vector dimension (e.g., 384 for MiniLM)

**`LocalEmbeddingService`** — uses `sentence-transformers` with `all-MiniLM-L6-v2`:
- 384 dimensions, 22MB model, CPU inference
- Auto-downloads model on first use (cached in `~/.cache/torch/sentence_transformers/`)
- Batch support (up to 32 texts)

**`OllamaEmbeddingService`** — uses Ollama's `/api/embeddings` endpoint:
- Model: `nomic-embed-text` (768 dimensions)
- Requires Ollama running locally
- HTTP call to `http://localhost:11434/api/embeddings`

**`StubEmbeddingService`** — returns zero vectors (for tests, no ML deps needed)

### Dependencies

```toml
[project.optional-dependencies]
ml = ["sentence-transformers>=3.0.0", "onnxruntime>=1.18.0", "transformers>=4.40.0", "optimum[onnxruntime]>=1.19.0"]
```

### Python memory changes (`tiered_memory.py`)

- `TieredMemoryService.__init__()` gains optional `embedding_service: EmbeddingService | None`
- `store()`: compute and store embedding alongside entry when service available
- `recall()`: semantic search via cosine similarity when service available; BM25 word-overlap fallback otherwise
- New field: `ColdEntry.embedding: list[float] | None = None`

### Rust memory changes (`sqlite_memory.rs`)

- Add `embedding BLOB` column to memories table (little-endian f32 bytes)
- New function: `cosine_similarity(a: &[f32], b: &[f32]) -> f32`
- Modified `recall()`: combine cosine similarity with FTS5 BM25 (0.7 semantic + 0.3 BM25) when embedding provided

### New Brain MCP tool

- `memory_search_semantic` — semantic recall using embeddings

### Tests (~12 new)

- Embedding service ABC contract
- Local embed produces correct dimensions
- Ollama embed (mocked HTTP)
- Cosine similarity function (Rust)
- Semantic recall outperforms word-overlap on synonym queries
- Stub fallback preserves backward compat
- Combined BM25+semantic scoring
- Null embedding handling
- Batch embedding

---

## 2. Persistent Registry (Weeks 3-4)

### Goal

Replace in-memory registry with SQLite-backed persistence. Add cross-node sync for distributed deployments.

### New file: `ygn-core/src/sqlite_registry.rs`

**`SqliteRegistry`** implementing existing `NodeRegistry` trait:
- Database: `$YGN_DATA_DIR/registry.db` (default: `~/.ygn/registry.db`)
- WAL mode (consistent with SqliteMemory)
- Schema:
  ```sql
  CREATE TABLE nodes (
      node_id TEXT PRIMARY KEY,
      role TEXT NOT NULL,
      trust_tier INTEGER NOT NULL,
      endpoints TEXT NOT NULL,    -- JSON array
      capabilities TEXT NOT NULL, -- JSON array
      last_seen TEXT NOT NULL,    -- ISO 8601
      metadata TEXT DEFAULT '{}'
  );
  CREATE INDEX idx_nodes_role ON nodes(role);
  CREATE INDEX idx_nodes_last_seen ON nodes(last_seen);
  ```

### Heartbeat eviction

Background tokio task runs every 60 seconds, removes nodes with `last_seen` older than `max_staleness_sec` (default 300s).

### Self-registration

On `ygn-core gateway` startup, auto-register this node in local SQLite registry with role, endpoints, capabilities.

### Cross-node sync (gossip over HTTP)

- Each node periodically POSTs its local node list to peers: `POST /registry/sync`
- Peers merge incoming nodes (INSERT OR REPLACE if newer `last_seen`)
- Peer list from config: `[registry] seeds = ["http://10.0.0.1:3000"]`
- Eventual consistency, last-writer-wins on `last_seen`
- New endpoint: `POST /registry/sync` — accepts `{nodes: [...]}`, returns `{accepted: N, rejected: N}`

### A2A integration

- `GET /.well-known/agent.json` pulls capabilities from registry instead of hardcoded card
- New A2A `SendMessage` from unknown agent → optional auto-registration

### Gateway API

- `GET /registry/nodes` — list all nodes (optional role/trust filter)
- `GET /registry/nodes/{id}` — specific node info
- `DELETE /registry/nodes/{id}` — deregister (admin)
- `POST /registry/sync` — cross-node sync endpoint

### Config

```toml
[registry]
backend = "sqlite"           # "memory" | "sqlite"
path = "~/.ygn/registry.db"
heartbeat_interval_sec = 30
max_staleness_sec = 300
sync_interval_sec = 60
seeds = []
```

### Tests (~10 new)

- SQLite CRUD: register, discover, heartbeat, deregister
- Filter combinations: role + trust_tier + staleness
- Heartbeat eviction: insert stale node, verify evicted
- Self-registration on gateway startup
- Cross-node sync: two registries merge correctly
- API endpoints: /registry/nodes returns JSON

---

## 3. ML-Based Guard (Weeks 5-6)

### Goal

Add real ML classifier for prompt injection detection. Local-only inference via ONNX Runtime or Ollama. Zero external API calls.

### Model choices

**Primary**: `meta-llama/Prompt-Guard-86M` — 86M params, purpose-built for prompt injection. ONNX export, ~5-15ms CPU inference.

**Alternative**: `microsoft/deberta-v3-base` fine-tuned on injection datasets. Larger (184M) but more general.

**Ollama option**: Any instruction-following model with classification system prompt. Simpler setup, lower accuracy, higher latency.

### New file: `ygn-brain/src/ygn_brain/guard_ml.py`

**`OnnxClassifierGuard`** extending `ClassifierGuard`:
- Auto-downloads PromptGuard from HF Hub (cached in `~/.ygn/models/`)
- ONNX inference via `onnxruntime`
- `classify(text) -> (is_safe, threat_score)` via softmax on model output

**`OllamaClassifierGuard`** extending `ClassifierGuard`:
- Calls Ollama chat completion with classification system prompt
- Parses structured output (JSON mode) for is_safe + confidence
- Higher latency (~200-500ms) but no model download needed

### GuardPipeline integration

```python
pipeline = GuardPipeline(guards=[
    RegexGuard(),               # Fast pre-filter (microseconds)
    OnnxClassifierGuard(),      # ML classifier (5-15ms)
    ToolInvocationGuard(...)    # Tool-level checks
])
```

**Performance optimization**: If regex already blocks (score >= 75), ML guard is skipped.

**Score aggregation**: `max(scores)` across all backends (existing behavior).

### Guard statistics

New `GET /guard/stats` endpoint:
```json
{
  "total_checks": 1547,
  "blocked": 23,
  "threat_levels": {"NONE": 1480, "LOW": 34, "MEDIUM": 10, "HIGH": 15, "CRITICAL": 8},
  "avg_latency_ms": 4.2,
  "model": "prompt-guard-86m"
}
```

Exposed via new `guard_stats` Brain MCP tool.

### Benchmark suite

`tests/test_guard_benchmark.py` (gated behind `@pytest.mark.slow`):
- Run 10 Red/Blue attack templates through RegexGuard-only vs RegexGuard+ML
- Compare detection rates
- Verify ML catches unicode homoglyphs, base64, synonym bypass

### Config

```
YGN_GUARD_MODEL=prompt-guard-86m   # or deberta-v3-injection, ollama
YGN_GUARD_BACKEND=onnx             # or ollama
YGN_MODELS_DIR=~/.ygn/models/
```

### Tests (~10 new)

- ONNX model loading (stub for CI)
- classify() returns valid scores
- ML catches unicode homoglyph that regex misses
- Pipeline: RegexGuard + OnnxClassifierGuard
- Fast-path: regex blocks, ML skipped
- Ollama guard (mocked HTTP)
- Guard stats accumulation
- StubClassifierGuard backward compat

---

## 4. Governance Dashboard — ygn-dash (Weeks 7-8)

### Goal

Cross-platform Tauri desktop app showing real-time governance status.

### Project structure

```
ygn-dash/
├── src-tauri/
│   ├── Cargo.toml           — Tauri 2, serde, reqwest, rusqlite
│   ├── src/
│   │   ├── main.rs          — Tauri app entry
│   │   ├── commands.rs      — IPC commands
│   │   └── db.rs            — Direct SQLite reads
│   └── tauri.conf.json
├── src/
│   ├── App.tsx              — Router + layout
│   ├── pages/
│   │   ├── Dashboard.tsx    — Overview: status cards, provider health, recent events
│   │   ├── GuardLog.tsx     — Guard decision timeline (filterable)
│   │   ├── EvidenceViewer.tsx — Evidence Pack browser + hash chain verification
│   │   ├── NodeRegistry.tsx — Active nodes, roles, health
│   │   └── MemoryExplorer.tsx — Tier breakdown, search, entry detail
│   ├── components/
│   │   ├── StatusCard.tsx
│   │   ├── Timeline.tsx
│   │   ├── HashChainView.tsx
│   │   └── TierChart.tsx
│   └── lib/
│       ├── api.ts           — HTTP client for ygn-core
│       └── tauri.ts         — IPC wrappers
├── package.json             — bun, react 18, typescript, tailwind v4, recharts
├── tsconfig.json
├── vite.config.ts
└── index.html
```

### Data sources

1. **Direct SQLite** (local mode) — reads `registry.db` and `memory.db` via rusqlite in Tauri backend. Fast, works offline.
2. **HTTP API** (remote mode) — calls ygn-core gateway endpoints. Works with remote deployments.

Default: auto-detect (SQLite first, HTTP fallback).

### Pages

**Dashboard** (landing):
- 4 status cards: Core Status, Guard (checks + blocked), Nodes (active), Memory (entries)
- Provider health grid with latency sparklines
- Recent guard events feed (last 10)

**Guard Log**:
- Filterable timeline of guard decisions
- Each entry: timestamp, input preview, threat level (color), score, backend, reason
- Click detail: full input, all scores, Evidence Pack link

**Evidence Viewer**:
- List by session ID
- Entry-by-entry view with hash chain visualization
- Inline verification (hash chain + signatures)
- Export as JSONL/JSON

**Node Registry**:
- Table: ID, role, trust tier, endpoints, last seen, health
- Role filter
- Heartbeat timeline per node
- Sync status

**Memory Explorer**:
- Tier breakdown chart (pie: Hot/Warm/Cold)
- Search: BM25 / semantic / hybrid toggle
- Entry detail: content, tags, tier, embedding preview, timestamps

### Tech stack

- Tauri 2, React 18, TypeScript, Tailwind CSS v4, Recharts, Bun

### New gateway endpoints

```
GET  /guard/stats          — check counts, block rates, latency
GET  /guard/log            — paginated guard decision log
GET  /sessions             — Evidence Pack session list
GET  /sessions/{id}        — export specific Evidence Pack
GET  /memory/stats         — tier distribution, entry counts
```

### Tests (~8 new)

- Tauri IPC commands return expected shapes
- Gateway new endpoints return valid JSON
- Frontend components render without crash (vitest + testing-library)

---

## New gateway endpoints summary

| Endpoint | Method | Section | Description |
|----------|--------|---------|-------------|
| `/registry/nodes` | GET | 2 | List registered nodes |
| `/registry/nodes/{id}` | GET | 2 | Get node by ID |
| `/registry/nodes/{id}` | DELETE | 2 | Deregister node |
| `/registry/sync` | POST | 2 | Cross-node registry sync |
| `/guard/stats` | GET | 3 | Guard statistics |
| `/guard/log` | GET | 4 | Paginated guard log |
| `/sessions` | GET | 4 | Evidence Pack list |
| `/sessions/{id}` | GET | 4 | Export Evidence Pack |
| `/memory/stats` | GET | 4 | Memory tier stats |

---

## Dependencies summary

### Python (ygn-brain)

**Required** (added to base deps):
- (none — all new deps are optional)

**Optional** (`[project.optional-dependencies].ml`):
- `sentence-transformers>=3.0.0`
- `onnxruntime>=1.18.0`
- `transformers>=4.40.0`
- `optimum[onnxruntime]>=1.19.0`

### Rust (ygn-core)

- `rusqlite` — already present (used by sqlite_memory)
- No new crate dependencies for registry

### Tauri (ygn-dash)

- `tauri>=2.0.0`
- `rusqlite` (in Tauri backend)
- `reqwest` (in Tauri backend)
- React 18, TypeScript, Tailwind CSS v4, Recharts, Bun

---

## Test count estimate

| Section | New tests | Cumulative |
|---------|-----------|------------|
| Embeddings | ~12 | 692 |
| Registry | ~10 | 702 |
| ML Guard | ~10 | 712 |
| Dashboard | ~8 | 720 |
| **Total** | **~40** | **~720** |

---

## Success criteria

1. `pytest -v` — all tests pass (existing 336 + ~22 new Python)
2. `cargo test --target x86_64-pc-windows-msvc` — all tests pass (existing 344 + ~10 new Rust)
3. `bun run tauri build` (ygn-dash) — builds successfully
4. Semantic memory recall outperforms word-overlap on synonym queries
5. ML guard catches attacks that regex misses (unicode, base64, synonym)
6. Registry persists across ygn-core restarts
7. Dashboard displays live data from ygn-core gateway
8. `ruff check` — clean
9. Evidence Pack hash chain verifiable in dashboard UI

---

## Risk register

| Risk | Impact | Mitigation |
|------|--------|------------|
| PromptGuard model download fails in CI | Tests fail | Stub model for CI, real model tests gated behind `@pytest.mark.slow` |
| sentence-transformers heavy install | Slow CI, large dep | Optional dependency, stub for tests |
| Tauri 2 Windows build issues | Dashboard blocked | Follow opcode patterns (proven on this machine) |
| SQLite WAL lock contention (dashboard + core) | Read failures | Dashboard opens in read-only mode (`SQLITE_OPEN_READONLY`) |
| Cross-node sync introduces split-brain | Stale registry | Last-writer-wins is acceptable for discovery; not used for authorization |

# v0.7.0 Hardening Sprint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire all stub endpoints to real data, make the Refinement Harness use real CLI providers, fix doc drift, and align MCP transport — turning Y-GN into a fact-first, E2E-proven runtime.

**Architecture:** 4 phases: (1) fix doc drift, (2) wire Harness to real providers + update model IDs, (3) wire all gateway endpoints to persistent storage (SQLite for guard log, JSONL for evidence, shared registry), (4) MCP error code alignment. Each phase is independently testable.

**Tech Stack:** Python 3.11+ (existing providers), Rust (rusqlite, axum, serde_json), Codex CLI (gpt-5.3-codex), Gemini CLI (gemini-3.1-pro-preview).

**Design doc:** `docs/plans/2026-02-26-v070-hardening-design.md`

---

## Phase 1: Doc Drift Fix

### Task 1: README fact-first rewrite

**Files:**
- Modify: `README.md` (lines 3, 46-59, 128-134)

**Step 1: Read README.md**

Read the full file to understand current structure.

**Step 2: Fix version**

Line 3: change `v0.5.0` to `v0.7.0`.

**Step 3: Replace "Roadmap / Known Stubs" section (lines 46-59)**

Replace with two sections:

```markdown
## Works Today (E2E verified)

| Feature | File/Symbol | Verify Command |
|---------|------------|----------------|
| MCP Brain↔Core | `ygn-core/src/mcp.rs` | `cargo test mcp` |
| CLI providers (Codex+Gemini) | `codex_provider.py`, `gemini_provider.py` | `pytest tests/test_codex_provider.py -v` |
| Evidence Pack (hash chain + ed25519 + Merkle) | `evidence.py` | `pytest tests/test_evidence.py -v` |
| Guard pipeline (regex + ML stub) | `guard.py`, `guard_ml.py` | `pytest tests/test_guard.py -v` |
| Persistent registry (SQLite) | `sqlite_registry.rs` | `cargo test sqlite_registry` |
| Memory (3-tier + embeddings + Temporal KG) | `tiered_memory.py` | `pytest tests/test_temporal_kg.py -v` |
| Brain MCP server (7 tools) | `mcp_server.py` | `pytest tests/test_mcp_server.py -v` |
| Refinement Harness (Poetiq-inspired) | `harness/engine.py` | `pytest tests/test_harness_engine.py -v` |
| Governance Dashboard (Tauri) | `ygn-dash/` | `cd ygn-dash && bun run build` |

## Planned / Partially Wired

| Feature | Status | Blocker |
|---------|--------|---------|
| WASM/WASI sandbox | Stub (Wassette integration ready) | Wassette binary not on Windows |
| Landlock OS sandbox | Stub (types exist) | Linux-only |
| Real ML guard model | Code ready, model not bundled | Run `ygn-brain-guard-download` |
```

**Step 4: Update test counts (lines 128-134)**

Will be updated in final task after all changes.

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: README fact-first rewrite — Works Today + Planned sections"
```

---

## Phase 2: Harness Réel Multi-Provider

### Task 2: Update Codex model to gpt-5.3-codex

**Files:**
- Modify: `ygn-brain/src/ygn_brain/codex_provider.py` (line 21)

**Step 1: Change `_DEFAULT_MODEL`**

Line 21: `"gpt-5.2-codex"` → `"gpt-5.3-codex"`

**Step 2: Run existing tests**

```bash
cd ygn-brain && python -m pytest tests/test_codex_provider.py tests/test_codex_hardening.py -v
```

**Step 3: Commit**

```bash
git add ygn-brain/src/ygn_brain/codex_provider.py
git commit -m "feat(codex): update default model to gpt-5.3-codex"
```

---

### Task 3: Wire orchestrate_refined to real providers

**Files:**
- Modify: `ygn-brain/src/ygn_brain/mcp_server.py` (lines 298-326, specifically line 313)

**Step 1: Read current implementation**

Read `mcp_server.py` lines 298-326 to understand `_call_orchestrate_refined()`.

**Step 2: Replace StubCandidateGenerator with conditional logic**

Replace the import block (around line 304) and generator instantiation (line 313):

```python
async def _call_orchestrate_refined(self, args: dict) -> dict:
    from ygn_brain.harness import (
        ConsensusSelector,
        DefaultPolicy,
        HarnessConfig,
        MultiProviderGenerator,
        RefinementHarness,
        StubCandidateGenerator,
        TextVerifier,
    )

    task = args.get("task", "")
    max_rounds = args.get("max_rounds", 3)
    ensemble = args.get("ensemble", False)

    providers = ["gemini", "codex"] if ensemble else ["stub"]
    use_real = ensemble or any(
        p in providers for p in ("codex", "gemini")
    )

    generator = (
        MultiProviderGenerator()
        if use_real
        else StubCandidateGenerator(output=f"Refined response for: {task}")
    )

    harness = RefinementHarness(
        generator=generator,
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=max_rounds, min_score=0.5),
        selector=ConsensusSelector(),
    )
    config = HarnessConfig(
        providers=providers, max_rounds=max_rounds, ensemble=ensemble,
    )
    result = await harness.run(task, config)
    return {
        "winner": result.winner.output,
        "provider": result.winner.provider,
        "model": result.winner.model,
        "score": result.feedback.score,
        "rounds": result.rounds_used,
        "candidates": result.total_candidates,
    }
```

**Step 3: Run unit tests (non-E2E)**

```bash
cd ygn-brain && python -m pytest tests/test_mcp_server.py -v -k "not e2e"
```

**Step 4: Commit**

```bash
git add ygn-brain/src/ygn_brain/mcp_server.py
git commit -m "feat(harness): wire orchestrate_refined to real MultiProviderGenerator"
```

---

## Phase 3: Wire Persistence

### Task 4: Guard log SQLite persistence (Python side)

**Files:**
- Create: `ygn-brain/src/ygn_brain/guard_log.py`
- Create: `ygn-brain/tests/test_guard_log.py`

**Step 1: Write failing tests**

```python
# ygn-brain/tests/test_guard_log.py
"""Tests for persistent guard log."""

import tempfile
import os
from ygn_brain.guard_log import GuardLog
from ygn_brain.guard import GuardResult, ThreatLevel


def test_guard_log_write_and_read():
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "guard_log.db")
        log = GuardLog(db_path)
        log.record(
            input_text="test input",
            result=GuardResult(
                allowed=True,
                threat_level=ThreatLevel.NONE,
                reason="ok",
                score=0.0,
            ),
            backend="RegexGuard",
        )
        entries = log.list_entries(limit=10)
        assert len(entries) == 1
        assert entries[0]["allowed"] is True
        assert entries[0]["backend"] == "RegexGuard"


def test_guard_log_stats():
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "guard_log.db")
        log = GuardLog(db_path)
        log.record("safe", GuardResult(True, ThreatLevel.NONE, "ok", 0.0), "Regex")
        log.record("bad", GuardResult(False, ThreatLevel.HIGH, "blocked", 80.0), "ML")
        stats = log.stats()
        assert stats["total_checks"] == 2
        assert stats["blocked"] == 1


def test_guard_log_empty():
    with tempfile.TemporaryDirectory() as td:
        log = GuardLog(os.path.join(td, "guard_log.db"))
        assert log.list_entries() == []
        assert log.stats()["total_checks"] == 0
```

**Step 2: Implement**

```python
# ygn-brain/src/ygn_brain/guard_log.py
"""Persistent guard log backed by SQLite."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from ygn_brain.guard import GuardResult


class GuardLog:
    """SQLite-backed guard check log."""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS guard_checks (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                input_preview TEXT NOT NULL,
                threat_level TEXT NOT NULL,
                score REAL NOT NULL,
                backend TEXT NOT NULL,
                reason TEXT NOT NULL,
                allowed INTEGER NOT NULL
            )"""
        )
        self._conn.commit()

    def record(
        self, input_text: str, result: GuardResult, backend: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO guard_checks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex[:12],
                datetime.now(tz=timezone.utc).isoformat(),
                input_text[:200],
                result.threat_level.value,
                result.score,
                backend,
                result.reason,
                1 if result.allowed else 0,
            ),
        )
        self._conn.commit()

    def list_entries(self, limit: int = 50, offset: int = 0) -> list[dict]:
        cursor = self._conn.execute(
            "SELECT * FROM guard_checks ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        entries = []
        for row in rows:
            entry = dict(zip(cols, row, strict=True))
            entry["allowed"] = bool(entry["allowed"])
            entries.append(entry)
        return entries

    def stats(self) -> dict:
        cursor = self._conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN allowed=0 THEN 1 ELSE 0 END) as blocked, "
            "AVG(score) as avg_score FROM guard_checks"
        )
        row = cursor.fetchone()
        total = row[0] or 0
        blocked = row[1] or 0
        return {
            "total_checks": total,
            "blocked": blocked,
            "avg_score": round(row[2] or 0.0, 2),
        }
```

**Step 3: Run tests + ruff + commit**

```bash
cd ygn-brain && python -m pytest tests/test_guard_log.py -v
git add ygn-brain/src/ygn_brain/guard_log.py ygn-brain/tests/test_guard_log.py
git commit -m "feat(guard): add persistent GuardLog backed by SQLite"
```

---

### Task 5: Wire gateway /guard/log and /guard/stats to real data

**Files:**
- Modify: `ygn-core/src/gateway.rs` (lines 184-209)

**Step 1: Replace stub handlers**

Replace `guard_log()` (lines 184-190) to read from `~/.ygn/guard_log.db`:

```rust
async fn guard_log() -> Json<Value> {
    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .unwrap_or_else(|_| ".".to_string());
    let db_path = format!("{home}/.ygn/guard_log.db");

    match rusqlite::Connection::open_with_flags(
        &db_path,
        rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY | rusqlite::OpenFlags::SQLITE_OPEN_NO_MUTEX,
    ) {
        Ok(conn) => {
            let mut stmt = conn
                .prepare("SELECT id, timestamp, input_preview, threat_level, score, backend, reason, allowed FROM guard_checks ORDER BY timestamp DESC LIMIT 50")
                .unwrap();
            let entries: Vec<Value> = stmt
                .query_map([], |row| {
                    Ok(json!({
                        "id": row.get::<_, String>(0)?,
                        "timestamp": row.get::<_, String>(1)?,
                        "input_preview": row.get::<_, String>(2)?,
                        "threat_level": row.get::<_, String>(3)?,
                        "score": row.get::<_, f64>(4)?,
                        "backend": row.get::<_, String>(5)?,
                        "reason": row.get::<_, String>(6)?,
                        "allowed": row.get::<_, i32>(7)? != 0,
                    }))
                })
                .unwrap()
                .filter_map(|r| r.ok())
                .collect();
            let count = entries.len();
            Json(json!({ "entries": entries, "count": count }))
        }
        Err(_) => Json(json!({ "entries": [], "count": 0 })),
    }
}
```

Similarly for `guard_stats`:
```rust
async fn guard_stats() -> Json<Value> {
    // Same DB open pattern, run aggregate query
}
```

Note: Add `guard_stats` route if not already present. Check if `/guard/stats` route exists in `build_router()`.

**Step 2: Add tests, build, commit**

```bash
cd ygn-core && cargo test --target x86_64-pc-windows-msvc gateway -- --skip credential_vault::tests::drop_zeros
git add ygn-core/src/gateway.rs
git commit -m "feat(gateway): wire /guard/log and /guard/stats to SQLite"
```

---

### Task 6: Wire gateway /sessions to real Evidence Pack files

**Files:**
- Modify: `ygn-core/src/gateway.rs` (lines 193-199)

**Step 1: Replace `sessions_list()` stub**

Scan `~/.ygn/evidence/` directory for `.jsonl` files, read first line of each for metadata:

```rust
async fn sessions_list() -> Json<Value> {
    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .unwrap_or_else(|_| ".".to_string());
    let evidence_dir = format!("{home}/.ygn/evidence");

    let mut sessions: Vec<Value> = Vec::new();
    if let Ok(entries) = std::fs::read_dir(&evidence_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().map(|e| e == "jsonl").unwrap_or(false) {
                let id = path.file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or("unknown")
                    .to_string();
                let metadata = std::fs::metadata(&path).ok();
                let size = metadata.as_ref().map(|m| m.len()).unwrap_or(0);
                sessions.push(json!({
                    "id": id,
                    "file": path.to_string_lossy(),
                    "size_bytes": size,
                }));
            }
        }
    }
    let count = sessions.len();
    Json(json!({ "sessions": sessions, "count": count }))
}
```

**Step 2: Test + commit**

```bash
cd ygn-core && cargo test --target x86_64-pc-windows-msvc gateway
git add ygn-core/src/gateway.rs
git commit -m "feat(gateway): wire /sessions to real Evidence Pack JSONL files"
```

---

### Task 7: Wire /memory/stats to Brain MCP

**Files:**
- Modify: `ygn-core/src/gateway.rs` (lines 202-209)

**Step 1: Replace `memory_stats()` stub**

For now, return a meaningful structure that indicates the endpoint is wired but requires Brain connection:

```rust
async fn memory_stats() -> Json<Value> {
    // In production, this would call Brain MCP memory_recall
    // For now, return real structure with zero counts indicating "no brain connected"
    Json(json!({
        "hot_count": 0,
        "warm_count": 0,
        "cold_count": 0,
        "total": 0,
        "status": "no_brain_connection",
        "note": "Connect Brain MCP server for real stats",
    }))
}
```

This is minimally different from the stub but adds the `status` field so the dashboard can distinguish "no data" from "endpoint not implemented".

**Step 2: Commit**

```bash
git add ygn-core/src/gateway.rs
git commit -m "feat(gateway): /memory/stats returns structured status"
```

---

### Task 8: Wire registry to shared SqliteRegistry via Axum State

**Files:**
- Modify: `ygn-core/src/gateway.rs` (lines 121-122 for a2a, 130-158 for registry)

**Step 1: Read gateway.rs**

Understand how routes are currently set up. The `build_router()` doesn't use Axum State currently.

**Step 2: Add shared state**

This is the most complex task. Add an `AppState` struct:

```rust
use std::sync::Arc;

pub struct AppState {
    pub registry: Arc<crate::sqlite_registry::SqliteRegistry>,
    pub a2a_tasks: Arc<crate::a2a::SqliteTaskStore>,
}
```

Modify `build_router()` to accept state:
```rust
pub fn build_router(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health))
        // ... all routes ...
        .with_state(state)
}
```

Modify `list_registry_nodes` and `a2a_handler` to extract state:
```rust
async fn list_registry_nodes(State(state): State<AppState>) -> Json<Value> {
    let filter = DiscoveryFilter { ... };
    let nodes = state.registry.discover(filter).await.unwrap_or_default();
    // ... serialize ...
}
```

**Important**: This changes the router signature, so ALL existing tests that use `test_router()` need updating. The test helper must create an `AppState` with `:memory:` databases.

**Step 3: Update tests, build, commit**

```bash
cd ygn-core && cargo test --target x86_64-pc-windows-msvc -- --skip credential_vault::tests::drop_zeros
git add ygn-core/src/gateway.rs
git commit -m "feat(gateway): shared AppState with persistent SqliteRegistry + SqliteTaskStore"
```

---

## Phase 4: MCP Alignment

### Task 9: MCP error code constants + Accept header

**Files:**
- Modify: `ygn-core/src/mcp.rs`
- Modify: `ygn-core/src/gateway.rs` (mcp_http handler)

**Step 1: Verify existing error handling**

Read `mcp.rs`. Error codes -32601 and -32602 exist. Add -32600 (invalid request) if missing.

**Step 2: Add Accept header parsing in mcp_http**

In gateway.rs `mcp_http()` handler, parse the Accept header:
- If `text/event-stream` → respond with SSE (for now, just respond JSON and log a warning)
- If `application/json` or default → respond with JSON (current behavior)

**Step 3: Add integration test**

```rust
#[tokio::test]
async fn mcp_http_returns_proper_error_for_invalid_method() {
    let app = test_router();
    let body = serde_json::to_string(&json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "nonexistent/method",
        "params": {}
    })).unwrap();
    let response = app.oneshot(
        Request::builder()
            .method("POST")
            .uri("/mcp")
            .header("content-type", "application/json")
            .body(Body::from(body))
            .unwrap(),
    ).await.unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let bytes = response.into_body().collect().await.unwrap().to_bytes();
    let json: Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(json["error"]["code"], -32601);
}
```

**Step 4: Commit**

```bash
git add ygn-core/src/mcp.rs ygn-core/src/gateway.rs
git commit -m "feat(mcp): add -32600 error code + Accept header awareness"
```

---

## Final Integration

### Task 10: Version bump + exports + final lint + docs

**Files:**
- Modify: `ygn-brain/pyproject.toml`, `ygn-brain/src/ygn_brain/__init__.py`, `ygn-core/Cargo.toml`
- Modify: `CHANGELOG.md`, `CLAUDE.md`, `memory-bank/*`

**Step 1: Bump versions to 0.7.0**

**Step 2: Add GuardLog to exports**

In `__init__.py`, add:
```python
from .guard_log import GuardLog
```

**Step 3: Run full test suites**

```bash
cd ygn-brain && ruff check . --fix && ruff format . && python -m pytest -q --tb=short -k "not e2e"
cd ygn-core && cargo fmt && cargo clippy --target x86_64-pc-windows-msvc -- -D warnings
cd ygn-core && cargo test --target x86_64-pc-windows-msvc
cd ygn-dash && bun run build
```

**Step 4: Update CHANGELOG, CLAUDE.md, memory-bank**

**Step 5: Commit**

```bash
git add -A
git commit -m "docs: v0.7.0 Hardening Sprint — Truth & Wiring release notes"
```

---

## Test count estimate

| Task | New tests |
|------|-----------|
| T4: GuardLog SQLite | 3 |
| T5: Gateway guard/log wiring | 1 |
| T6: Gateway sessions wiring | 1 |
| T8: Shared AppState | 2 (update existing) |
| T9: MCP error codes | 1 |
| **Total** | **~8 new** |

Expected: **~825+ tests** total.

# Y-GN v0.7.0 — Hardening Sprint "Truth & Wiring"

**Date**: 2026-02-26
**Source**: analyse2.md + web research (Feb 2026)
**Theme**: Stop placeholders, wire everything for real, docs that never lie
**Priorities** (from analyse2.md):
1. Stop placeholders (endpoints & wiring)
2. Refinement Harness réel multi-provider (Codex+Gemini CLI)
3. Docs qui ne mentent jamais

---

## Context & Research

### Model IDs (validated Feb 2026)
- **Codex CLI**: `gpt-5.3-codex` (released Feb 5 2026, 25% faster than 5.2)
  - Source: [OpenAI — Introducing GPT-5.3-Codex](https://openai.com/index/introducing-gpt-5-3-codex/)
- **Gemini CLI**: `gemini-3.1-pro-preview` (accessible via `/model` command)
  - Source: [Gemini CLI — Gemini 3 Pro and Flash](https://geminicli.com/docs/get-started/gemini-3/)
  - Note: availability varies by subscription tier

### MCP Streamable HTTP (spec 2025-03-26)
- Single endpoint, POST for JSON-RPC, GET for SSE streams
- Accept header determines response format (`application/json` or `text/event-stream`)
- Source: [MCP Transports Specification](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)

### analyse2.md Key Findings
- Endpoints `/guard/log`, `/sessions`, `/memory/stats` return empty arrays (placeholders)
- Registry handler creates `:memory:` SQLite per request (not shared state)
- `orchestrate_refined` MCP tool uses StubCandidateGenerator (not real providers)
- README at v0.5.0 with obsolete "Known stubs" section

---

## Phase 0: Baseline & Truth (no code changes)

Produce a **capability truth table**:
| Claim (docs/changelog) | Code reality (file+symbol) | E2E reality (command) |

Run full test suites, attempt manual golden path:
1. Start ygn-core gateway
2. Start ygn-brain MCP server
3. Invoke `orchestrate_refined` via MCP
4. Save EvidencePack, verify signature + hash chain + merkle root

---

## Phase 1: Doc Drift Fix

### README.md
- Version: current → `v0.7.0`
- Remove outdated "Known stubs" section
- Add "Works Today (E2E verified)" section with links to file/symbol + command
- Add "Planned / Partially Wired" section for real stubs (Landlock, Wassette)

### Test count updates
- All docs: update to actual test counts after hardening

---

## Phase 2: Harness Réel Multi-Provider

### Problem
`orchestrate_refined` MCP tool hardcodes `StubCandidateGenerator`. Real providers never called.

### Solution
1. In `mcp_server.py/_call_orchestrate_refined()`: use `MultiProviderGenerator` when `ensemble=True`
2. Update `codex_provider.py` `_DEFAULT_MODEL`: `"gpt-5.2-codex"` → `"gpt-5.3-codex"`
3. Verify Gemini CLI model flag (`--model gemini-3.1-pro-preview`)
4. E2E test: real `orchestrate_refined` call producing signed Evidence Pack

### Deliverables
- Each candidate stores: provider name, model ID, latency, token count
- Every iteration traced in EvidencePack
- EvidencePack signed if `YGN_EVIDENCE_SIGNING_KEY` set; `verify()` passes

---

## Phase 3: Wire Persistence (stop returning placeholders)

### Guard Log — SQLite (`~/.ygn/guard_log.db`)
- Table: `guard_checks (id, timestamp, input_preview, threat_level, score, backend, reason, allowed)`
- `GuardPipeline.evaluate()` writes each result
- `GET /guard/log` reads from SQLite (with pagination: `?limit=50&offset=0`)
- `GET /guard/stats` aggregates from SQLite (COUNT, AVG latency, threat distribution)

### Evidence Sessions — JSONL (`~/.ygn/evidence/`)
- `EvidencePack.save()` already writes JSONL — no change
- `GET /sessions` scans directory, reads metadata from each file
- `GET /sessions/{id}` reads the specific JSONL file

### Memory Stats
- `GET /memory/stats` returns tier counts from TieredMemoryService internal state
- Read `len(_hot)`, `len(_warm)`, `len(_cold)` directly

### Registry — Shared SqliteRegistry via Axum State
- Replace `SqliteRegistry::new(":memory:")` per-request with shared `Arc<SqliteRegistry>`
- Registry file: `~/.ygn/registry.db` (configurable via `YGN_REGISTRY_PATH`)
- Gateway self-registers on startup
- `registry_sync` also uses shared state

---

## Phase 4: MCP Streamable HTTP Alignment

### Current state
`POST /mcp` handles JSON-RPC 2.0 via `handle_jsonrpc()`. Basic error handling exists.

### Improvements
1. Parse `Accept` header: `text/event-stream` → SSE response, `application/json` → JSON response
2. Add proper JSON-RPC error codes: -32700 (parse error), -32600 (invalid request), -32601 (method not found)
3. Integration test: POST valid JSON-RPC → validate response structure

---

## File changes summary

| File | Phase | Change |
|------|-------|--------|
| README.md | 1 | Version + fact-first rewrite |
| codex_provider.py | 2 | `_DEFAULT_MODEL` → `gpt-5.3-codex` |
| mcp_server.py | 2 | `orchestrate_refined` uses real providers |
| guard.py | 3 | Write guard results to SQLite |
| gateway.rs | 3,4 | Wire endpoints to real data, shared registry, MCP error codes |
| a2a.rs | 3 | Wire `handle_a2a` to `SqliteTaskStore` |
| CLAUDE.md | 1 | Version + test counts |
| memory-bank/* | 1 | Progress, context, decisions |

---

## Test plan

| Phase | New tests | Type |
|-------|-----------|------|
| 1 | 0 | (doc only) |
| 2 | 2 | E2E (real CLI) |
| 3 | 6 | Unit (SQLite guard log, sessions scan, memory stats, shared registry) |
| 4 | 2 | Integration (MCP error codes, Accept header) |
| **Total** | **~10** | |

---

## Success criteria

1. `GET /guard/log` returns real guard check history from SQLite
2. `GET /sessions` returns real Evidence Pack sessions from disk
3. `GET /memory/stats` returns real tier counts
4. Registry endpoints use shared persistent state
5. `orchestrate_refined` runs with real Codex+Gemini CLI and produces signed Evidence Pack
6. README "Works Today" section has E2E-verifiable commands for every claimed feature
7. MCP `/mcp` returns proper JSON-RPC error codes
8. All tests pass, lint clean

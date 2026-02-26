# Y-GN Refinement Harness — Design Document

**Date**: 2026-02-26
**Inspiration**: [Poetiq harness](https://poetiq.ai/posts/raising_the_bar_hle_simpleqa/), [ARC Prize 2025 Technical Report](https://arxiv.org/html/2601.10904v1), [ARC Prize 2025 Results Analysis](https://arcprize.org/blog/arc-prize-2025-results-analysis)
**Approach**: Option 1 — Generic Refinement Engine (Poetiq is a preset)
**Constraints**: Zero API cost (Codex CLI + Gemini CLI only), full EvidencePack tracing

---

## Why This Works (Poetiq × ARC Prize × Y-GN mapping)

**Poetiq** demonstrates that a "meta-system using LLMs to build/improve/pilot task-specific systems" improves every model tested. Their harness achieves 54% on ARC-AGI-2 (up from 31% baseline) via multi-model ensemble, adaptive verification, and hierarchical problem bucketing.

**ARC Prize 2025** identifies the central theme: "refinement loop — iteratively transforming one program into a better one based on a feedback signal." Domain-specific harnesses at the application layer meaningfully improve commercial model reliability.

**Y-GN already has the building blocks**:
- EvidencePack (signed, tamper-evident) → traces every iteration
- Swarm (parallel/sequential/red-blue) → generates multiple candidates
- Guard (regex + ML) → filters injections during exploration
- Memory (embeddings + hybrid retrieval) → capitalizes winning patterns
- Brain MCP server → exposes harness as tool to external agents
- ProviderFactory → Codex + Gemini CLI with zero API cost

---

## Architecture: 5 Components

```
                    ┌──────────────────────────────────────┐
                    │          RefinementHarness            │
                    │                                      │
  task ──────►  CandidateGenerator ──► N candidats         │
                    │                    │                  │
                    │              Verifier ──► Feedback    │
                    │                    │                  │
                    │          RefinementPolicy             │
                    │           (continue? refine?)         │
                    │                    │                  │
                    │              Selector ──► best        │
                    │                    │                  │
                    │          MemoryStore ──► capitalize   │
                    │                                      │
                    │   EvidencePack traces each step       │
                    └──────────────────────────────────────┘
```

### 1. CandidateGenerator

**ABC**: `generate(task, context, config) -> list[Candidate]`

**MultiProviderGenerator** implementation:
- Uses `ProviderFactory` to instantiate Codex CLI + Gemini CLI
- Generates N candidates per provider (configurable)
- Supports multiple temperatures per provider
- Handles rate limiting gracefully (Gemini 3.1 Pro has low usage rates)

**Gemini models** (via `YGN_GEMINI_MODEL` env var):
- `gemini-3-flash` — fast, higher rate limits, default for candidate generation
- `gemini-3.1-pro-preview` — most capable, lower rate limits, for complex tasks
- Automatic fallback to `gemini-2.5-pro` when rate limited

**Codex models**: model `5.3` if configurable, via `codex exec`

### 2. Verifier

**ABC**: `verify(candidate, task) -> Feedback`

**Feedback dataclass**:
```python
@dataclass
class Feedback:
    passed: bool
    score: float         # 0.0 - 1.0
    diagnostics: str     # human-readable explanation
    artifacts: dict      # test output, logs, etc.
```

**TextVerifier** — checks coherence, format, no refusal, minimum length. Score via heuristics.

**CommandVerifier** — executes shell command (pytest, cargo test, ruff), captures stdout/stderr, score = tests_passed / tests_total.

### 3. RefinementPolicy

**ABC**: `should_continue(round, best_score, history) -> bool` + `refine_prompt(task, feedback) -> str`

**DefaultPolicy**:
- Continue if `round < max_rounds` AND `best_score < min_score`
- Refine prompt by appending verifier diagnostics as context
- No retry on same exact prompt (track seen prompts)

### 4. Selector

**ABC**: `select(candidates_with_feedback) -> Candidate`

**ConsensusSelector**:
- Primary: highest verifier score
- Bonus: +0.1 if 2+ providers converge (cosine similarity on outputs > 0.85)
- Tie-break: lowest latency

### 5. MemoryStore

**HarnessMemoryStore** — uses existing `TieredMemoryService`:
- `store_pattern(task, winning_candidate, feedback)` — stores to COLD tier with embedding
- `recall_patterns(task, limit=3)` — semantic recall of past winning patterns
- Patterns include: effective prompt structure, best provider, verification strategy

---

## EvidencePack Integration

Each harness run traces to a dedicated EvidencePack:

| Phase | Kind | Data |
|-------|------|------|
| generation | `candidate` | provider, model, prompt_hash, output_hash, latency_ms |
| verification | `verification` | candidate_id, score, passed, diagnostics |
| refinement | `decision` | round, action (continue/stop), reason |
| selection | `selection` | winner_id, consensus_score, total_candidates |
| memory | `pattern` | task_hash, pattern_key, recall_count |

All entries: SHA-256 hash chain + Merkle root + optional ed25519 signature.

---

## Presets

```python
POETIQ_PRESET = HarnessConfig(
    max_rounds=3,
    min_score=0.8,
    ensemble=True,
    providers=["gemini", "codex"],
    candidates_per_provider=2,
    verifier="text",           # or "command"
)
```

---

## MCP Exposure

New Brain MCP tool: `orchestrate_refined`
```json
{
    "name": "orchestrate_refined",
    "description": "Run refinement harness with multi-provider ensemble",
    "inputSchema": {
        "properties": {
            "task": {"type": "string"},
            "max_rounds": {"type": "integer", "default": 3},
            "ensemble": {"type": "boolean", "default": true},
            "providers": {"type": "array", "items": {"type": "string"}},
            "verifier": {"type": "string", "enum": ["text", "command"]}
        },
        "required": ["task"]
    }
}
```

---

## Drift Fixes (included in this version)

| Drift | Location | Fix |
|-------|----------|-----|
| README v0.2.1 | README.md:3 | Update to v0.5.0, fix test counts to 783 |
| MCP serverInfo.version "0.3.0" | mcp_server.py:164 | Import `__version__` dynamically |
| Registry :memory: per request | gateway.rs:131 | Document as known limitation (no code change) |

---

## File Structure

```
ygn-brain/src/ygn_brain/harness/
├── __init__.py          — exports
├── types.py             — Candidate, Feedback, HarnessResult, HarnessConfig, POETIQ_PRESET
├── candidate.py         — CandidateGenerator ABC + MultiProviderGenerator
├── verifier.py          — Verifier ABC + TextVerifier + CommandVerifier
├── policy.py            — RefinementPolicy ABC + DefaultPolicy
├── selector.py          — Selector ABC + ConsensusSelector
├── memory_store.py      — HarnessMemoryStore
└── engine.py            — RefinementHarness (main loop)
```

---

## Test Plan

**Unit tests (~15)**:
- CandidateGenerator ABC + stub
- TextVerifier scoring
- CommandVerifier subprocess
- DefaultPolicy stop conditions
- ConsensusSelector scoring + consensus bonus
- MemoryStore store/recall
- Engine loop (max_rounds, min_score stop)
- EvidencePack entries for each phase
- HarnessConfig + POETIQ_PRESET

**E2E tests (3, `@pytest.mark.e2e`)**:
1. Gemini seul (gemini-3-flash), task simple, rounds=2 → produces response
2. Ensemble Codex+Gemini → consensus selection works
3. Evidence export → JSONL valid + Merkle root + signature if key provided

---

## Sources

- [Poetiq: Raising the Bar (HLE, SimpleQA)](https://poetiq.ai/posts/raising_the_bar_hle_simpleqa/)
- [Poetiq: ARC-AGI Verified](https://poetiq.ai/posts/arcagi_verified/)
- [ARC Prize 2025 Technical Report](https://arxiv.org/html/2601.10904v1)
- [ARC Prize 2025 Results Analysis](https://arcprize.org/blog/arc-prize-2025-results-analysis)
- [Gemini 3 Pro/Flash on Gemini CLI](https://geminicli.com/docs/get-started/gemini-3/)
- [Gemini 3.1 Pro announcement](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-pro/)

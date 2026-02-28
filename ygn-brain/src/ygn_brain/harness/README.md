# harness

Poetiq-inspired refinement harness — generate-verify-refine loop for iteratively
improving outputs via multi-provider ensemble.

## How It Works

```
Task → CandidateGenerator → [Candidate, Candidate, ...]
                                    ↓
                              Verifier.verify() → Feedback (score, diagnostics)
                                    ↓
                              RefinementPolicy.should_continue()?
                                ├─ yes → refine prompt → generate again
                                └─ no  → ConsensusSelector.select() → winner
```

## Modules

| File | Purpose |
|------|---------|
| `engine.py` | `RefinementHarness` — main generate-verify-refine loop |
| `types.py` | `Candidate`, `Feedback`, `HarnessConfig`, `HarnessResult`, `POETIQ_PRESET` |
| `candidate.py` | `CandidateGenerator` ABC, `MultiProviderGenerator`, `StubCandidateGenerator` |
| `verifier.py` | `Verifier` ABC, `TextVerifier` (heuristic scoring), `CommandVerifier` (exit code) |
| `policy.py` | `RefinementPolicy` ABC, `DefaultPolicy` (round + score thresholds) |
| `selector.py` | `Selector` ABC, `ConsensusSelector` (group by output + consensus bonus) |
| `memory_store.py` | `HarnessMemoryStore` — persists winning patterns to cold memory |

## Usage

```python
from ygn_brain.harness import (
    RefinementHarness, StubCandidateGenerator, TextVerifier,
    DefaultPolicy, ConsensusSelector, HarnessConfig,
)

harness = RefinementHarness(
    generator=StubCandidateGenerator(output="Hello"),
    verifier=TextVerifier(),
    policy=DefaultPolicy(max_rounds=3, min_score=0.5),
    selector=ConsensusSelector(),
)

config = HarnessConfig(providers=["stub"], max_rounds=3)
result = await harness.run("Write a greeting", config)
print(result.winner.output, result.feedback.score)
```

## Tests

```bash
pytest tests/test_harness_engine.py tests/test_harness_types.py \
       tests/test_harness_candidate.py tests/test_harness_verifier.py \
       tests/test_harness_policy.py tests/test_harness_e2e.py -v
```

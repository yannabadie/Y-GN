# context_compiler

AgentOS-inspired context compilation pipeline for ygn-brain.

## Problem

LLM context windows are finite. Putting everything (full history, raw tool outputs,
all memories) into the prompt wastes tokens and degrades quality ("lost in the middle").

## Solution

Separate **ground truth** (Session/EventLog — everything that happened) from the
**compiled view** (WorkingContext — what the LLM actually sees), connected by a
configurable processor pipeline with explicit token budget.

## Architecture

```
Session(EventLog)  →  ContextCompiler  →  WorkingContext
    ↑                    ↓ processors       ↓
    |              HistorySelector      to_messages() → LLM
    |              Compactor
    |              MemoryPreloader
  record()         ArtifactAttacher → ArtifactStore
```

## Modules

| File | Purpose |
|------|---------|
| `session.py` | `Session`, `EventLog`, `SessionEvent` — append-only ground truth wrapping `EvidencePack` |
| `working_context.py` | `WorkingContext` — budget-aware compiled view with `to_messages()` for LLM calls |
| `processors.py` | `ContextCompiler` + 4 processors: `HistorySelector`, `Compactor`, `MemoryPreloader`, `ArtifactAttacher` |
| `artifact_store.py` | `ArtifactStore` ABC + `SqliteArtifactStore` + `FsArtifactStore` (content-addressed, SHA-256) |
| `token_budget.py` | `TokenBudget` tracker + `estimate_tokens()` heuristic |

## Usage

```python
from ygn_brain.context_compiler import (
    Session, ContextCompiler, HistorySelector, Compactor,
    ArtifactAttacher, SqliteArtifactStore,
)

# 1. Create session (ground truth)
session = Session()
session.record("user_input", {"text": "Analyze logs"}, token_estimate=10)

# 2. Build processor pipeline
store = SqliteArtifactStore(db_path="artifacts.db")
compiler = ContextCompiler(processors=[
    HistorySelector(keep_first=2, keep_last=5),
    Compactor(),
    ArtifactAttacher(artifact_store=store, threshold_bytes=1024),
])

# 3. Compile within budget
ctx = compiler.compile(session, budget=4000, system_prompt="You are helpful.")
messages = ctx.to_messages()  # ready for provider.chat()
```

## Custom Processors

Any class with a `name` attribute and `process(session, ctx, budget) -> WorkingContext`
method satisfies the `Processor` protocol:

```python
class MyProcessor:
    name = "my_processor"

    def process(self, session, ctx, budget):
        # transform ctx...
        return ctx
```

## Demo

```bash
python -m ygn_brain.demo_compiler
```

## Tests

```bash
pytest tests/test_session.py tests/test_token_budget.py tests/test_working_context.py \
       tests/test_artifact_store.py tests/test_processors.py tests/test_context_compiler_e2e.py -v
```

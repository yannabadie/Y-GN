# tool_interrupt

Typed tool events, normalization, and schema validation for MCP tool calls.

## Problem

Tool calls via MCP are fire-and-forget: the bridge returns a raw string with no
structured handling of success/error/timeout, no normalization of outputs, and no
protection against secrets leaking into LLM context.

## Solution

`ToolInterruptHandler` wraps `McpToolBridge` with:
1. **Typed events** — every tool interaction produces a `ToolEvent` (CALL/SUCCESS/ERROR/TIMEOUT)
2. **Timeout** — `asyncio.wait_for` with configurable deadline
3. **Normalization** — `PerceptionAligner` validates output schemas, redacts secrets, generates summaries
4. **Externalization** — large results stored in `ArtifactStore`, replaced with handles

## Architecture

```
ToolInterruptHandler.call(tool_name, args)
    ├─ Record CALL event → Session
    ├─ Execute via McpToolBridge (with timeout)
    ├─ PerceptionAligner.normalize()
    │   ├─ JSON parse
    │   ├─ SchemaRegistry.validate()
    │   ├─ Redact secrets (API keys, tokens, passwords)
    │   └─ Generate concise + detailed summaries
    ├─ Externalize if large → ArtifactStore
    └─ Record SUCCESS/ERROR/TIMEOUT event → Session
```

## Modules

| File | Purpose |
|------|---------|
| `events.py` | `ToolEvent` dataclass + `ToolEventKind` enum (CALL, SUCCESS, ERROR, TIMEOUT) |
| `handler.py` | `ToolInterruptHandler` — wraps bridge with events, timeout, normalization |
| `normalizer.py` | `PerceptionAligner` — schema validation + secret redaction + summaries |
| `schemas.py` | `SchemaRegistry` — per-tool output JSON Schema validation |

## Usage

```python
from ygn_brain.tool_interrupt import (
    ToolInterruptHandler, PerceptionAligner, SchemaRegistry, ToolEventKind,
)
from ygn_brain.context_compiler import Session, SqliteArtifactStore

# Setup
registry = SchemaRegistry()
registry.register("calc", {
    "type": "object",
    "properties": {"result": {"type": "number"}},
    "required": ["result"],
})

handler = ToolInterruptHandler(
    bridge=mcp_bridge,
    normalizer=PerceptionAligner(schema_registry=registry),
    session=Session(),
    artifact_store=SqliteArtifactStore(db_path="artifacts.db"),
)

# Call a tool with timeout
event = await handler.call("calc", {"expr": "2+2"}, timeout_sec=10.0)

if event.kind == ToolEventKind.SUCCESS:
    print(event.result)
    print(event.normalized["summary_concise"])
elif event.kind == ToolEventKind.TIMEOUT:
    print(f"Timed out: {event.error}")
```

## Secret Redaction Patterns

The `PerceptionAligner` automatically redacts:
- API keys (`sk-...`)
- Bearer tokens (`Bearer eyJ...`)
- Passwords (`password=...`)
- GitHub tokens (`ghp_...`, `gho_...`)
- Generic secrets (`secret=...`, `api_key=...`)

## Tests

```bash
pytest tests/test_tool_events.py tests/test_normalizer.py tests/test_tool_interrupt.py -v
```

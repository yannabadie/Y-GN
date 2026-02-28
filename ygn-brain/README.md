# ygn-brain

Python cognitive control-plane for Y-GN — orchestration, multi-agent swarm, evidence packs, context compilation.

## Install

```bash
pip install -e .[dev]
```

Optional ML dependencies (embeddings, prompt injection detection):

```bash
pip install -e .[ml]
```

## Quality Gates

```bash
ruff check .
mypy src/
pytest -q
```

## CLI Commands

```bash
ygn-brain-mcp                  # Start Brain MCP server over stdio
ygn-brain-repl                 # Interactive REPL
ygn-brain-guard-download       # Download PromptGuard-86M model
ygn-brain-demo-compiler        # Demo: context compiler with artifact externalization
```

## Package Structure

```
src/ygn_brain/
  orchestrator.py          # Mediator: run() / run_async() / run_compiled()
  hivemind.py              # 7-phase pipeline (diagnosis → synthesis)
  context.py               # ExecutionContext builder
  fsm.py                   # Phase state machine
  evidence.py              # EvidencePack (SHA-256 hash chain + ed25519 + Merkle)
  guard.py                 # GuardPipeline (RegexGuard, ToolInvocationGuard)
  guard_ml.py              # ML-based guards (ONNX, Ollama)
  swarm.py                 # Multi-mode swarm (Parallel, Sequential, RedBlue, ...)
  memory.py                # MemoryService ABC
  tiered_memory.py         # 3-tier memory (hot/warm/cold)
  embeddings.py            # EmbeddingService (sentence-transformers, Ollama)
  mcp_server.py            # Brain MCP server (8 tools)
  mcp_client.py            # Brain→Core MCP client
  tool_bridge.py           # McpToolBridge wrapper
  provider.py              # LLMProvider ABC + StubLLMProvider
  codex_provider.py        # Codex CLI provider
  gemini_provider.py       # Gemini CLI provider
  context_compiler/        # AgentOS-inspired context compilation
  tool_interrupt/          # Typed tool events + normalization
  harness/                 # Refinement Harness (generate-verify-refine)
```

## Brain MCP Tools

| Tool | Description |
|------|-------------|
| `orchestrate` | Run full HiveMind pipeline |
| `guard_check` | Evaluate input against Guard pipeline |
| `evidence_export` | Export Evidence Pack as JSONL |
| `swarm_execute` | Run Swarm with specific mode |
| `memory_recall` | Query 3-tier memory |
| `memory_search_semantic` | Semantic recall (vector embeddings) |
| `orchestrate_refined` | Refinement harness with multi-provider ensemble |
| `orchestrate_compiled` | Context-compiled pipeline with token budget |

## Test Count

475 tests (2026-02-28).

## License

Apache-2.0

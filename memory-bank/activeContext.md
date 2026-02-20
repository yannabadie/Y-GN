# Active Context

## Current Focus

- [2026-02-20] All milestones + post-MVP COMPLETE — 0 Planned items remaining
- Full system: 9 milestones + 2 post-MVP sprints, 580 tests
- Multi-provider LLM support: Claude, OpenAI/Codex, Gemini, Ollama

## Completed Today

- Multi-provider LLM adapters (Rust): Claude, OpenAI, Gemini, Ollama
- ProviderRegistry with smart model routing
- Credential vault with zero-on-drop security
- Token-bucket rate limiter per provider
- Provider health tracking + circuit breaker
- Python LLM provider abstraction + ProviderRouter + ModelSelector
- HiveMind pipeline with async LLM execution
- SwarmEngine with async LLM-backed execution modes
- Discord + Matrix channel adapters
- Landlock OS sandbox (cross-platform)
- Tunnel management (cloudflared/tailscale/ngrok)
- Conversation memory with context window limits
- Agent personality system with 4 built-in personas
- Enhanced gateway: /providers + /health/providers
- Interactive REPL (sync + async)

## Test Counts

- Rust: 336 tests (333 unit + 3 smoke integration)
- Python: 244 tests
- Total: 580 tests, all green

## Current Blockers

- None — capability matrix 100% complete
- Real LLM calls require API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY)

# Active Context

## Current Focus

- [2026-02-20] Multi-provider LLM support complete
- Full roadmap M0–M8 executed + post-MVP + multi-provider
- System supports Claude, OpenAI/Codex, Gemini, Ollama

## Completed Today

- Multi-provider LLM adapters (Rust): Claude, OpenAI, Gemini, Ollama
- ProviderRegistry with smart model routing
- Credential vault with zero-on-drop security
- Token-bucket rate limiter per provider
- Provider health tracking + circuit breaker
- Python LLM provider abstraction + ProviderRouter
- HiveMind pipeline with async LLM execution
- Orchestrator with async provider support

## Test Counts

- Rust: 276+ tests
- Python: 195+ tests
- Total: 471+ tests, all green

## Current Blockers

- None — system fully operational with stub providers
- Real LLM calls require API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY)

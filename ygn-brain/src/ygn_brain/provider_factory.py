"""Provider factory — deterministic provider selection from environment."""

from __future__ import annotations

import os
import shutil

from .codex_provider import CodexCliProvider
from .gemini_provider import GeminiCliProvider
from .provider import LLMProvider, StubLLMProvider

# Valid provider names for YGN_LLM_PROVIDER
_VALID_PROVIDERS = frozenset({"codex", "gemini", "stub"})


class ProviderFactory:
    """Creates the appropriate LLM provider based on configuration.

    Resolution logic (deterministic, no magic):
        1. Read ``YGN_LLM_PROVIDER`` env var (codex | gemini | stub).
        2. If set: return that exact provider (fail-fast if CLI missing).
        3. If unset and ``fallback=True``: try codex -> gemini -> stub.
        4. If unset and ``fallback=False`` (default): return stub.
    """

    @staticmethod
    def create(fallback: bool = False) -> LLMProvider:
        """Create a provider based on ``YGN_LLM_PROVIDER`` environment variable.

        Args:
            fallback: If True and ``YGN_LLM_PROVIDER`` is not set, try
                codex -> gemini -> stub in order of availability.
                If False (default), return stub when env is unset.

        Returns:
            An LLMProvider instance.

        Raises:
            ValueError: If ``YGN_LLM_PROVIDER`` is set to an unknown value.
        """
        env_provider = os.environ.get("YGN_LLM_PROVIDER", "").strip().lower()

        if env_provider:
            return ProviderFactory._create_explicit(env_provider)

        if fallback:
            return ProviderFactory._create_fallback()

        return StubLLMProvider()

    @staticmethod
    def _create_explicit(provider_name: str) -> LLMProvider:
        """Create a specific provider by name."""
        if provider_name not in _VALID_PROVIDERS:
            msg = (
                f"Unknown provider '{provider_name}'. "
                f"Valid values for YGN_LLM_PROVIDER: {', '.join(sorted(_VALID_PROVIDERS))}"
            )
            raise ValueError(msg)

        if provider_name == "codex":
            return CodexCliProvider()
        if provider_name == "gemini":
            return GeminiCliProvider()
        return StubLLMProvider()

    @staticmethod
    def _create_fallback() -> LLMProvider:
        """Auto-detect available CLI providers, fall back to stub."""
        if shutil.which("codex") is not None:
            return CodexCliProvider()
        if shutil.which("gemini") is not None:
            return GeminiCliProvider()
        return StubLLMProvider()

    @staticmethod
    def describe(provider: LLMProvider) -> str:
        """Return a human-readable description of a provider for REPL output."""
        name = provider.name()
        if name == "codex" and isinstance(provider, CodexCliProvider):
            return f"CodexCliProvider (model={provider.model})"
        if name == "gemini" and isinstance(provider, GeminiCliProvider):
            return f"GeminiCliProvider (model={provider.model})"
        if name == "stub":
            return "StubLLMProvider (deterministic responses)"
        return f"{type(provider).__name__}"

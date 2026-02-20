"""Provider routing — maps model names to providers and selects models for tasks."""

from __future__ import annotations

from .provider import LLMProvider
from .swarm import TaskComplexity

# ---------------------------------------------------------------------------
# Pattern-based model-name prefixes
# ---------------------------------------------------------------------------

_PREFIX_MAP: dict[str, str] = {
    "claude": "claude",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "gemini": "gemini",
    "llama": "ollama",
    "mistral": "ollama",
    "phi": "ollama",
}


class ProviderRouter:
    """Routes model names to providers and manages provider lifecycle."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._model_map: dict[str, str] = {}  # model_name -> provider_name
        self._default: str | None = None

    # -- registration -------------------------------------------------------

    def register(self, provider: LLMProvider) -> None:
        """Register a provider under its canonical name."""
        self._providers[provider.name()] = provider

    def set_default(self, provider_name: str) -> None:
        """Set the default provider used when no mapping matches."""
        if provider_name not in self._providers:
            msg = f"Unknown provider: {provider_name}"
            raise KeyError(msg)
        self._default = provider_name

    def map_model(self, model_name: str, provider_name: str) -> None:
        """Explicitly map a model name to a registered provider."""
        if provider_name not in self._providers:
            msg = f"Unknown provider: {provider_name}"
            raise KeyError(msg)
        self._model_map[model_name] = provider_name

    # -- lookup -------------------------------------------------------------

    def route(self, model_name: str) -> LLMProvider:
        """Resolve a model name to its provider.

        Resolution order:
        1. Exact match in ``_model_map``.
        2. Prefix match via ``_PREFIX_MAP``.
        3. Default provider (if set).
        4. Raise ``KeyError``.
        """
        # 1. Explicit mapping
        if model_name in self._model_map:
            return self._providers[self._model_map[model_name]]

        # 2. Prefix heuristic
        lower = model_name.lower()
        for prefix, provider_name in _PREFIX_MAP.items():
            if lower.startswith(prefix):
                if provider_name in self._providers:
                    return self._providers[provider_name]

        # 3. Default
        if self._default is not None:
            return self._providers[self._default]

        msg = f"No provider found for model '{model_name}'"
        raise KeyError(msg)

    def get(self, provider_name: str) -> LLMProvider:
        """Get a provider by its canonical name."""
        if provider_name not in self._providers:
            msg = f"Unknown provider: {provider_name}"
            raise KeyError(msg)
        return self._providers[provider_name]

    def list_providers(self) -> list[str]:
        """Return sorted list of registered provider names."""
        return sorted(self._providers)

    # -- factory ------------------------------------------------------------

    @classmethod
    def with_defaults(cls) -> ProviderRouter:
        """Create a router with standard prefix mappings pre-configured.

        No providers are registered — callers must still ``register()`` the
        providers they want to use.  The prefix map (claude-* -> claude,
        gpt-*/o1-*/o3-* -> openai, etc.) is handled automatically by
        ``route()``.
        """
        return cls()


# ---------------------------------------------------------------------------
# Model selector
# ---------------------------------------------------------------------------

# Maps (complexity, requires_tools) to a default model name.
_COMPLEXITY_MODELS: dict[TaskComplexity, str] = {
    TaskComplexity.TRIVIAL: "claude-3-haiku-20240307",
    TaskComplexity.SIMPLE: "claude-3-haiku-20240307",
    TaskComplexity.MODERATE: "claude-3-5-sonnet-20241022",
    TaskComplexity.COMPLEX: "claude-3-5-sonnet-20241022",
    TaskComplexity.EXPERT: "claude-3-opus-20240229",
}


class ModelSelector:
    """Selects the best model/provider for a given task based on complexity and requirements."""

    def __init__(self, router: ProviderRouter | None = None) -> None:
        self._router = router

    def select(
        self,
        task_complexity: TaskComplexity,
        requires_tools: bool = False,  # noqa: ARG002
        requires_vision: bool = False,
        preferred_provider: str | None = None,
    ) -> str:
        """Return the model name best suited for the task.

        If a *preferred_provider* is given and the router has it registered,
        we attempt to pick a model for that provider.  Otherwise we fall back
        to the complexity-based default.
        """
        # If caller prefers a specific provider, return a sensible model for it
        if preferred_provider is not None:
            return self._model_for_provider(
                preferred_provider, task_complexity, requires_vision
            )

        # Default: use the complexity map
        return _COMPLEXITY_MODELS.get(
            task_complexity, "claude-3-5-sonnet-20241022"
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _model_for_provider(
        provider: str,
        complexity: TaskComplexity,
        requires_vision: bool,  # noqa: ARG004
    ) -> str:
        """Pick a model name given a provider and complexity."""
        if provider == "openai":
            if complexity in {TaskComplexity.EXPERT, TaskComplexity.COMPLEX}:
                return "gpt-4o"
            return "gpt-4o-mini"
        if provider == "gemini":
            return "gemini-1.5-pro"
        if provider == "ollama":
            return "llama3"
        # Default to Claude
        return _COMPLEXITY_MODELS.get(complexity, "claude-3-5-sonnet-20241022")

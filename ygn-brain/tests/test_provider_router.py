"""Tests for provider_router module — ProviderRouter and ModelSelector."""

from __future__ import annotations

import pytest

from ygn_brain.provider import (
    StubLLMProvider,
)
from ygn_brain.provider_router import ModelSelector, ProviderRouter
from ygn_brain.swarm import TaskComplexity

# ---------------------------------------------------------------------------
# Helper: a second stub provider with a different name
# ---------------------------------------------------------------------------


class _OpenAIStub(StubLLMProvider):
    def name(self) -> str:
        return "openai"


class _GeminiStub(StubLLMProvider):
    def name(self) -> str:
        return "gemini"


class _OllamaStub(StubLLMProvider):
    def name(self) -> str:
        return "ollama"


class _ClaudeStub(StubLLMProvider):
    def name(self) -> str:
        return "claude"


# ---------------------------------------------------------------------------
# ProviderRouter — registration & lookup
# ---------------------------------------------------------------------------


def test_register_and_get_provider():
    router = ProviderRouter()
    stub = StubLLMProvider()
    router.register(stub)
    assert router.get("stub") is stub


def test_get_unknown_provider_raises():
    router = ProviderRouter()
    with pytest.raises(KeyError, match="Unknown provider"):
        router.get("nonexistent")


def test_list_providers_sorted():
    router = ProviderRouter()
    router.register(_OpenAIStub())
    router.register(_ClaudeStub())
    assert router.list_providers() == ["claude", "openai"]


# ---------------------------------------------------------------------------
# ProviderRouter — model routing
# ---------------------------------------------------------------------------


def test_route_claude_prefix():
    router = ProviderRouter()
    router.register(_ClaudeStub())
    provider = router.route("claude-3-opus-20240229")
    assert provider.name() == "claude"


def test_route_gpt_prefix():
    router = ProviderRouter()
    router.register(_OpenAIStub())
    provider = router.route("gpt-4o")
    assert provider.name() == "openai"


def test_route_o1_prefix():
    router = ProviderRouter()
    router.register(_OpenAIStub())
    provider = router.route("o1-preview")
    assert provider.name() == "openai"


def test_route_o3_prefix():
    router = ProviderRouter()
    router.register(_OpenAIStub())
    provider = router.route("o3-mini")
    assert provider.name() == "openai"


def test_route_gemini_prefix():
    router = ProviderRouter()
    router.register(_GeminiStub())
    provider = router.route("gemini-1.5-pro")
    assert provider.name() == "gemini"


def test_route_llama_prefix():
    router = ProviderRouter()
    router.register(_OllamaStub())
    provider = router.route("llama3")
    assert provider.name() == "ollama"


def test_route_explicit_model_map():
    router = ProviderRouter()
    router.register(_ClaudeStub())
    router.map_model("my-custom-model", "claude")
    provider = router.route("my-custom-model")
    assert provider.name() == "claude"


def test_route_explicit_map_overrides_prefix():
    router = ProviderRouter()
    router.register(_ClaudeStub())
    router.register(_OpenAIStub())
    # "gpt-custom" normally maps to openai via prefix
    router.map_model("gpt-custom", "claude")
    provider = router.route("gpt-custom")
    assert provider.name() == "claude"


def test_route_unknown_model_uses_default():
    router = ProviderRouter()
    router.register(StubLLMProvider())
    router.set_default("stub")
    provider = router.route("unknown-model-xyz")
    assert provider.name() == "stub"


def test_route_unknown_model_no_default_raises():
    router = ProviderRouter()
    with pytest.raises(KeyError, match="No provider found"):
        router.route("unknown-model")


def test_set_default_unknown_provider_raises():
    router = ProviderRouter()
    with pytest.raises(KeyError, match="Unknown provider"):
        router.set_default("bogus")


def test_map_model_unknown_provider_raises():
    router = ProviderRouter()
    with pytest.raises(KeyError, match="Unknown provider"):
        router.map_model("some-model", "bogus")


# ---------------------------------------------------------------------------
# ProviderRouter.with_defaults
# ---------------------------------------------------------------------------


def test_with_defaults_creates_router():
    router = ProviderRouter.with_defaults()
    assert isinstance(router, ProviderRouter)
    # No providers registered yet — just prefix mappings are active
    assert router.list_providers() == []


# ---------------------------------------------------------------------------
# ModelSelector
# ---------------------------------------------------------------------------


def test_selector_trivial_task():
    selector = ModelSelector()
    model = selector.select(TaskComplexity.TRIVIAL)
    assert "haiku" in model


def test_selector_expert_task():
    selector = ModelSelector()
    model = selector.select(TaskComplexity.EXPERT)
    assert "opus" in model


def test_selector_moderate_task():
    selector = ModelSelector()
    model = selector.select(TaskComplexity.MODERATE)
    assert "sonnet" in model


def test_selector_preferred_openai():
    selector = ModelSelector()
    model = selector.select(TaskComplexity.EXPERT, preferred_provider="openai")
    assert model.startswith("gpt")


def test_selector_preferred_gemini():
    selector = ModelSelector()
    model = selector.select(TaskComplexity.SIMPLE, preferred_provider="gemini")
    assert "gemini" in model


def test_selector_preferred_ollama():
    selector = ModelSelector()
    model = selector.select(TaskComplexity.SIMPLE, preferred_provider="ollama")
    assert "llama" in model

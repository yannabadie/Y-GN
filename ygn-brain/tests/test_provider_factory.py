"""Tests for ProviderFactory — env-based provider selection."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ygn_brain.codex_provider import CodexCliProvider
from ygn_brain.gemini_provider import GeminiCliProvider
from ygn_brain.provider import LLMProvider, StubLLMProvider
from ygn_brain.provider_factory import ProviderFactory

# ---------------------------------------------------------------------------
# Explicit provider selection via YGN_LLM_PROVIDER
# ---------------------------------------------------------------------------


def test_factory_creates_codex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YGN_LLM_PROVIDER", "codex")
    provider = ProviderFactory.create()
    assert isinstance(provider, CodexCliProvider)
    assert provider.name() == "codex"


def test_factory_creates_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YGN_LLM_PROVIDER", "gemini")
    provider = ProviderFactory.create()
    assert isinstance(provider, GeminiCliProvider)
    assert provider.name() == "gemini"


def test_factory_creates_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YGN_LLM_PROVIDER", "stub")
    provider = ProviderFactory.create()
    assert isinstance(provider, StubLLMProvider)
    assert provider.name() == "stub"


def test_factory_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YGN_LLM_PROVIDER", "unknown_provider")
    with pytest.raises(ValueError, match="Unknown provider"):
        ProviderFactory.create()


def test_factory_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YGN_LLM_PROVIDER", "CODEX")
    provider = ProviderFactory.create()
    assert isinstance(provider, CodexCliProvider)


def test_factory_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YGN_LLM_PROVIDER", "  gemini  ")
    provider = ProviderFactory.create()
    assert isinstance(provider, GeminiCliProvider)


# ---------------------------------------------------------------------------
# Default behavior (no YGN_LLM_PROVIDER set)
# ---------------------------------------------------------------------------


def test_factory_default_is_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YGN_LLM_PROVIDER", raising=False)
    provider = ProviderFactory.create()
    assert isinstance(provider, StubLLMProvider)


# ---------------------------------------------------------------------------
# Fallback mode
# ---------------------------------------------------------------------------


@patch("shutil.which")
def test_factory_fallback_codex_available(
    mock_which: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("YGN_LLM_PROVIDER", raising=False)

    def which_side(name: str) -> str | None:
        return "/usr/bin/codex" if name == "codex" else None

    mock_which.side_effect = which_side
    provider = ProviderFactory.create(fallback=True)
    assert isinstance(provider, CodexCliProvider)


@patch("shutil.which")
def test_factory_fallback_gemini_available(
    mock_which: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("YGN_LLM_PROVIDER", raising=False)

    def which_side(name: str) -> str | None:
        return "/usr/bin/gemini" if name == "gemini" else None

    mock_which.side_effect = which_side
    provider = ProviderFactory.create(fallback=True)
    assert isinstance(provider, GeminiCliProvider)


@patch("shutil.which", return_value=None)
def test_factory_fallback_nothing_available(
    mock_which: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("YGN_LLM_PROVIDER", raising=False)
    provider = ProviderFactory.create(fallback=True)
    assert isinstance(provider, StubLLMProvider)


# ---------------------------------------------------------------------------
# describe()
# ---------------------------------------------------------------------------


def test_describe_codex() -> None:
    p = CodexCliProvider(model="gpt-5.2-codex")
    desc = ProviderFactory.describe(p)
    assert "CodexCliProvider" in desc
    assert "gpt-5.2-codex" in desc


def test_describe_gemini() -> None:
    p = GeminiCliProvider(model="gemini-3.1-pro-preview")
    desc = ProviderFactory.describe(p)
    assert "GeminiCliProvider" in desc
    assert "gemini-3.1-pro-preview" in desc


def test_describe_stub() -> None:
    p = StubLLMProvider()
    desc = ProviderFactory.describe(p)
    assert "StubLLMProvider" in desc


def test_all_providers_are_llm_provider() -> None:
    """Every factory-created provider must be an LLMProvider."""
    for cls in (CodexCliProvider, GeminiCliProvider, StubLLMProvider):
        assert isinstance(cls(), LLMProvider)

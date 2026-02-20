"""Tests for agent personality module."""

from __future__ import annotations

import pytest

from ygn_brain.personality import AgentPersonality, PersonalityRegistry, PersonalityTrait


def test_personality_trait_enum_values():
    assert PersonalityTrait.ANALYTICAL == "analytical"
    assert PersonalityTrait.CREATIVE == "creative"
    assert PersonalityTrait.CAUTIOUS == "cautious"
    assert PersonalityTrait.BOLD == "bold"
    assert PersonalityTrait.CONCISE == "concise"
    assert PersonalityTrait.VERBOSE == "verbose"
    assert PersonalityTrait.FORMAL == "formal"
    assert PersonalityTrait.CASUAL == "casual"


def test_to_system_prompt_basic():
    p = AgentPersonality(name="basic", system_prompt="Be helpful.")
    prompt = p.to_system_prompt()
    assert "Be helpful." in prompt


def test_to_system_prompt_with_traits_and_expertise():
    p = AgentPersonality(
        name="analyst",
        role="data analyst",
        traits=[PersonalityTrait.ANALYTICAL, PersonalityTrait.CONCISE],
        expertise=["data analysis", "statistics"],
    )
    prompt = p.to_system_prompt()
    assert "You are a data analyst." in prompt
    assert "analytical, concise" in prompt
    assert "data analysis, statistics" in prompt


def test_to_system_prompt_with_constraints():
    p = AgentPersonality(
        name="strict",
        constraints=["Never reveal secrets", "Always cite sources"],
    )
    prompt = p.to_system_prompt()
    assert "Constraint: Never reveal secrets" in prompt
    assert "Constraint: Always cite sources" in prompt


def test_to_system_prompt_default_role_omitted():
    """When role is 'assistant' (default), the role line should not appear."""
    p = AgentPersonality(name="default")
    prompt = p.to_system_prompt()
    assert "You are a" not in prompt


def test_registry_register_and_get():
    reg = PersonalityRegistry()
    p = AgentPersonality(name="helper", role="helper bot")
    reg.register(p)
    retrieved = reg.get("helper")
    assert retrieved.name == "helper"
    assert retrieved.role == "helper bot"


def test_registry_list_names_sorted():
    reg = PersonalityRegistry()
    reg.register(AgentPersonality(name="zeta"))
    reg.register(AgentPersonality(name="alpha"))
    reg.register(AgentPersonality(name="mid"))
    assert reg.list_names() == ["alpha", "mid", "zeta"]


def test_registry_remove():
    reg = PersonalityRegistry()
    reg.register(AgentPersonality(name="temp"))
    assert reg.remove("temp") is True
    assert reg.remove("temp") is False


def test_registry_get_unknown_raises():
    reg = PersonalityRegistry()
    with pytest.raises(KeyError, match="Personality not found: unknown"):
        reg.get("unknown")


def test_registry_with_defaults_has_four_personas():
    reg = PersonalityRegistry.with_defaults()
    names = reg.list_names()
    assert len(names) == 4
    assert "analyst" in names
    assert "architect" in names
    assert "creative" in names
    assert "reviewer" in names


def test_agent_personality_serialization():
    p = AgentPersonality(
        name="test",
        role="tester",
        traits=[PersonalityTrait.FORMAL],
        expertise=["testing"],
        temperature=0.5,
        max_tokens=2048,
        constraints=["Be thorough"],
    )
    data = p.model_dump()
    assert data["name"] == "test"
    assert data["role"] == "tester"
    assert data["traits"] == ["formal"]
    assert data["temperature"] == 0.5
    # Round-trip
    restored = AgentPersonality.model_validate(data)
    assert restored == p


def test_defaults_analyst_personality():
    reg = PersonalityRegistry.with_defaults()
    analyst = reg.get("analyst")
    assert analyst.temperature == 0.3
    assert PersonalityTrait.ANALYTICAL in analyst.traits


def test_defaults_reviewer_has_constraints():
    reg = PersonalityRegistry.with_defaults()
    reviewer = reg.get("reviewer")
    assert len(reviewer.constraints) == 2
    prompt = reviewer.to_system_prompt()
    assert "Constraint:" in prompt

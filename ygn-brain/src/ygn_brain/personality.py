"""Agent personality system — configurable personas for LLM prompt construction."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PersonalityTrait(StrEnum):
    """Standard personality traits for agents."""

    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    CAUTIOUS = "cautious"
    BOLD = "bold"
    CONCISE = "concise"
    VERBOSE = "verbose"
    FORMAL = "formal"
    CASUAL = "casual"


class AgentPersonality(BaseModel):
    """Defines an agent's personality and behavior."""

    name: str
    role: str = "assistant"
    traits: list[PersonalityTrait] = Field(default_factory=list)
    system_prompt: str = ""
    expertise: list[str] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096
    constraints: list[str] = Field(default_factory=list)

    def to_system_prompt(self) -> str:
        """Generate a full system prompt from the personality definition."""
        parts: list[str] = []

        if self.system_prompt:
            parts.append(self.system_prompt)

        if self.role != "assistant":
            parts.append(f"You are a {self.role}.")

        if self.traits:
            trait_desc = ", ".join(t.value for t in self.traits)
            parts.append(f"Your communication style is: {trait_desc}.")

        if self.expertise:
            exp_desc = ", ".join(self.expertise)
            parts.append(f"Your areas of expertise include: {exp_desc}.")

        if self.constraints:
            for c in self.constraints:
                parts.append(f"Constraint: {c}")

        return "\n".join(parts)


class PersonalityRegistry:
    """Manages a collection of agent personalities."""

    def __init__(self) -> None:
        self._personalities: dict[str, AgentPersonality] = {}

    def register(self, personality: AgentPersonality) -> None:
        self._personalities[personality.name] = personality

    def get(self, name: str) -> AgentPersonality:
        if name not in self._personalities:
            raise KeyError(f"Personality not found: {name}")
        return self._personalities[name]

    def list_names(self) -> list[str]:
        return sorted(self._personalities.keys())

    def remove(self, name: str) -> bool:
        return self._personalities.pop(name, None) is not None

    @classmethod
    def with_defaults(cls) -> PersonalityRegistry:
        """Create a registry with built-in Y-GN agent personas."""
        registry = cls()

        registry.register(
            AgentPersonality(
                name="analyst",
                role="data analyst",
                traits=[PersonalityTrait.ANALYTICAL, PersonalityTrait.CONCISE],
                expertise=["data analysis", "statistics", "visualization"],
                temperature=0.3,
            )
        )

        registry.register(
            AgentPersonality(
                name="architect",
                role="software architect",
                traits=[PersonalityTrait.ANALYTICAL, PersonalityTrait.CAUTIOUS],
                expertise=["system design", "architecture patterns", "scalability"],
                temperature=0.5,
            )
        )

        registry.register(
            AgentPersonality(
                name="creative",
                role="creative problem solver",
                traits=[PersonalityTrait.CREATIVE, PersonalityTrait.BOLD],
                expertise=[
                    "brainstorming",
                    "ideation",
                    "unconventional solutions",
                ],
                temperature=0.9,
            )
        )

        registry.register(
            AgentPersonality(
                name="reviewer",
                role="code reviewer",
                traits=[
                    PersonalityTrait.ANALYTICAL,
                    PersonalityTrait.FORMAL,
                    PersonalityTrait.CAUTIOUS,
                ],
                expertise=["code quality", "security", "best practices"],
                temperature=0.2,
                constraints=[
                    "Always cite specific line numbers",
                    "Flag security issues first",
                ],
            )
        )

        return registry

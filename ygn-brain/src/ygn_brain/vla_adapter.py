"""VLA (Vision-Language-Action) Adapter — experimental bridge to hardware actions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class VLAInput:
    """Input to a VLA model (stub uses text description instead of actual image)."""

    image_description: str
    instruction: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class VLAOutput:
    """Output from a VLA model — a list of hardware actions."""

    actions: list[dict[str, Any]]
    confidence: float
    reasoning: str


# ---------------------------------------------------------------------------
# Adapter interface
# ---------------------------------------------------------------------------


class VLAAdapter(ABC):
    """Abstract base class for VLA adapters."""

    @abstractmethod
    async def predict(self, vla_input: VLAInput) -> VLAOutput:
        """Predict actions from a VLA input."""

    @abstractmethod
    def name(self) -> str:
        """Return the name of this adapter."""


# ---------------------------------------------------------------------------
# Stub implementation
# ---------------------------------------------------------------------------

# Keyword groups mapped to action types and base confidence.
_ACTION_KEYWORDS: dict[str, tuple[list[str], float]] = {
    "drive": (["move", "go", "navigate", "walk", "drive", "travel"], 0.85),
    "look": (["look", "see", "observe", "watch", "scan", "view"], 0.80),
    "speak": (["say", "speak", "tell", "announce", "ask", "report"], 0.90),
    "sense": (["measure", "sense", "check", "detect", "monitor", "read"], 0.75),
}


class StubVLAAdapter(VLAAdapter):
    """Keyword-based stub that maps instructions to hardware action dicts."""

    async def predict(self, vla_input: VLAInput) -> VLAOutput:
        """Map instruction keywords to hardware actions."""
        lower = vla_input.instruction.lower()
        actions: list[dict[str, Any]] = []
        total_confidence = 0.0
        reasons: list[str] = []

        for action_type, (keywords, base_confidence) in _ACTION_KEYWORDS.items():
            matched = [kw for kw in keywords if kw in lower]
            if matched:
                action: dict[str, Any] = {
                    "type": action_type,
                    "parameters": {
                        "instruction": vla_input.instruction,
                        "matched_keywords": matched,
                        "image_context": vla_input.image_description,
                    },
                }
                actions.append(action)
                total_confidence += base_confidence
                reasons.append(f"Matched '{action_type}' via keywords: {', '.join(matched)}")

        if not actions:
            # Unknown instruction — return a generic observe action with low confidence
            actions.append(
                {
                    "type": "observe",
                    "parameters": {
                        "instruction": vla_input.instruction,
                        "matched_keywords": [],
                        "image_context": vla_input.image_description,
                    },
                }
            )
            return VLAOutput(
                actions=actions,
                confidence=0.3,
                reasoning="No keyword match found; defaulting to observe action.",
            )

        avg_confidence = total_confidence / len(actions)
        return VLAOutput(
            actions=actions,
            confidence=round(min(avg_confidence, 1.0), 2),
            reasoning="; ".join(reasons),
        )

    def name(self) -> str:
        """Return adapter name."""
        return "stub-vla"


# ---------------------------------------------------------------------------
# VLA Bridge — connects VLA adapter to MCP tool calls
# ---------------------------------------------------------------------------


class VLABridge:
    """Bridges a VLA adapter to MCP-compatible tool call dicts."""

    def __init__(self, adapter: VLAAdapter) -> None:
        self._adapter = adapter

    async def plan_actions(self, image_desc: str, instruction: str) -> list[dict[str, Any]]:
        """Use the VLA adapter to predict actions, then return MCP-compatible tool calls.

        Each returned dict has ``tool_name`` and ``params`` keys, ready for
        consumption by an MCP tool bridge.
        """
        vla_input = VLAInput(image_description=image_desc, instruction=instruction)
        output = await self._adapter.predict(vla_input)

        tool_calls: list[dict[str, Any]] = []
        for action in output.actions:
            tool_calls.append(
                {
                    "tool_name": "hardware",
                    "params": {
                        "action_type": action["type"],
                        "parameters": action.get("parameters", {}),
                        "confidence": output.confidence,
                    },
                }
            )
        return tool_calls

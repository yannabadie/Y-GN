"""Tests for VLA adapter module — vision-language-action bridge."""

from __future__ import annotations

import pytest

from ygn_brain.vla_adapter import (
    StubVLAAdapter,
    VLABridge,
    VLAInput,
)

# ---------------------------------------------------------------------------
# StubVLAAdapter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stub_vla_predicts_move_action() -> None:
    """Instruction containing 'move' produces a drive action."""
    adapter = StubVLAAdapter()
    vla_input = VLAInput(
        image_description="A corridor",
        instruction="Move forward to the door",
    )
    output = await adapter.predict(vla_input)
    action_types = [a["type"] for a in output.actions]
    assert "drive" in action_types


@pytest.mark.asyncio
async def test_stub_vla_predicts_look_action() -> None:
    """Instruction containing 'look' produces a look action."""
    adapter = StubVLAAdapter()
    vla_input = VLAInput(
        image_description="A room",
        instruction="Look around the room",
    )
    output = await adapter.predict(vla_input)
    action_types = [a["type"] for a in output.actions]
    assert "look" in action_types


@pytest.mark.asyncio
async def test_stub_vla_predicts_speak_action() -> None:
    """Instruction containing 'say' produces a speak action."""
    adapter = StubVLAAdapter()
    vla_input = VLAInput(
        image_description="A person nearby",
        instruction="Say hello to the visitor",
    )
    output = await adapter.predict(vla_input)
    action_types = [a["type"] for a in output.actions]
    assert "speak" in action_types


@pytest.mark.asyncio
async def test_stub_vla_handles_unknown_instruction() -> None:
    """Unknown instruction falls back to observe with low confidence."""
    adapter = StubVLAAdapter()
    vla_input = VLAInput(
        image_description="Empty scene",
        instruction="Do something completely unexpected and unique",
    )
    output = await adapter.predict(vla_input)
    assert output.actions[0]["type"] == "observe"
    assert output.confidence <= 0.5


@pytest.mark.asyncio
async def test_vla_output_confidence_in_valid_range() -> None:
    """Confidence should be between 0.0 and 1.0 for all predictions."""
    adapter = StubVLAAdapter()
    instructions = [
        "Move to the left",
        "Look at the sky",
        "Tell me the temperature",
        "Random gibberish xyzzy",
    ]
    for instruction in instructions:
        vla_input = VLAInput(image_description="test", instruction=instruction)
        output = await adapter.predict(vla_input)
        assert 0.0 <= output.confidence <= 1.0


# ---------------------------------------------------------------------------
# VLABridge tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vla_bridge_produces_mcp_compatible_calls() -> None:
    """VLABridge.plan_actions returns dicts with tool_name and params keys."""
    adapter = StubVLAAdapter()
    bridge = VLABridge(adapter)
    calls = await bridge.plan_actions("A road", "Go forward quickly")
    assert len(calls) >= 1
    for call in calls:
        assert call["tool_name"] == "hardware"
        assert "action_type" in call["params"]
        assert "parameters" in call["params"]
        assert "confidence" in call["params"]

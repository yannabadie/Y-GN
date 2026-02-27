"""Tests for tool interrupt events."""

from ygn_brain.tool_interrupt.events import ToolEvent, ToolEventKind


def test_tool_event_kinds():
    assert ToolEventKind.CALL == "tool_call"
    assert ToolEventKind.SUCCESS == "tool_success"
    assert ToolEventKind.ERROR == "tool_error"
    assert ToolEventKind.TIMEOUT == "tool_timeout"


def test_tool_event_creation():
    evt = ToolEvent.create(
        kind=ToolEventKind.SUCCESS,
        tool_name="echo",
        arguments={"text": "hello"},
        result="hello",
        latency_ms=42.0,
    )
    assert evt.kind == ToolEventKind.SUCCESS
    assert evt.tool_name == "echo"
    assert evt.result == "hello"
    assert evt.error is None
    assert evt.latency_ms == 42.0
    assert evt.event_id  # non-empty


def test_tool_event_error():
    evt = ToolEvent.create(
        kind=ToolEventKind.ERROR,
        tool_name="fail_tool",
        arguments={},
        error="Connection refused",
        latency_ms=100.0,
    )
    assert evt.kind == ToolEventKind.ERROR
    assert evt.result is None
    assert evt.error == "Connection refused"

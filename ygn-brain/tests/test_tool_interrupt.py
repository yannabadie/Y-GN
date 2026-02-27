"""Tests for ToolInterruptHandler."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ygn_brain.context_compiler.artifact_store import SqliteArtifactStore
from ygn_brain.context_compiler.session import Session
from ygn_brain.tool_interrupt.events import ToolEventKind
from ygn_brain.tool_interrupt.handler import ToolInterruptHandler
from ygn_brain.tool_interrupt.normalizer import PerceptionAligner
from ygn_brain.tool_interrupt.schemas import SchemaRegistry


@pytest.fixture
def handler():
    bridge = AsyncMock()
    bridge.execute = AsyncMock(return_value="echo: hello")
    reg = SchemaRegistry()
    normalizer = PerceptionAligner(schema_registry=reg)
    session = Session()
    tmpdir = tempfile.mkdtemp()
    store = SqliteArtifactStore(db_path=Path(tmpdir) / "art.db")
    return ToolInterruptHandler(
        bridge=bridge, normalizer=normalizer, session=session, artifact_store=store,
    )


@pytest.mark.asyncio
async def test_handler_success(handler):
    event = await handler.call("echo", {"text": "hello"})
    assert event.kind == ToolEventKind.SUCCESS
    assert event.result == "echo: hello"
    assert event.error is None
    assert event.latency_ms >= 0
    # Session should have 2 events: CALL + SUCCESS
    assert len(handler._session.event_log.events) == 2


@pytest.mark.asyncio
async def test_handler_error(handler):
    handler._bridge.execute = AsyncMock(side_effect=RuntimeError("boom"))
    event = await handler.call("fail_tool", {})
    assert event.kind == ToolEventKind.ERROR
    assert event.error == "boom"
    assert event.result is None


@pytest.mark.asyncio
async def test_handler_timeout(handler):
    async def slow_execute(name, args):
        await asyncio.sleep(10)
        return "never"

    handler._bridge.execute = slow_execute
    event = await handler.call("slow_tool", {}, timeout_sec=0.1)
    assert event.kind == ToolEventKind.TIMEOUT
    assert event.error
    assert "timeout" in event.error.lower() or "timed out" in event.error.lower()

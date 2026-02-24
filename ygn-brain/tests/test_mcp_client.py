"""Tests for the MCP client and tool bridge."""

from __future__ import annotations

import json
import sys
import textwrap
from typing import Any

import pytest

from ygn_brain.mcp_client import _MCP_PROTOCOL_VERSION, McpClient, McpError
from ygn_brain.tool_bridge import McpToolBridge

# ---------------------------------------------------------------------------
# Helpers — inline mock MCP server script and fake process
# ---------------------------------------------------------------------------

# A tiny Python script that acts as a standards-compliant MCP server over stdio.
_MOCK_SERVER_SCRIPT = textwrap.dedent("""\
    import json, sys

    def respond(obj):
        sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\\n")
        sys.stdout.flush()

    for raw in sys.stdin:
        msg = json.loads(raw)
        method = msg.get("method", "")
        msg_id = msg.get("id")

        # Notifications have no id — ignore.
        if msg_id is None:
            continue

        if method == "initialize":
            respond({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "mock-core", "version": "0.0.1"},
                    "capabilities": {"tools": {}},
                },
            })
        elif method == "tools/list":
            respond({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echoes the provided input back as output",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "input": {
                                        "type": "string",
                                        "description": "Text to echo back",
                                    },
                                },
                                "required": ["input"],
                            },
                        }
                    ]
                },
            })
        elif method == "tools/call":
            name = msg["params"]["name"]
            args = msg["params"]["arguments"]
            if name == "echo":
                respond({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": args.get("input", "")}]
                    },
                })
            else:
                respond({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"},
                })
        else:
            respond({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            })
""")


def _mock_server_command() -> list[str]:
    """Return the command to launch the mock MCP server."""
    return [sys.executable, "-c", _MOCK_SERVER_SCRIPT]


# ---------------------------------------------------------------------------
# Unit tests — message formatting (no subprocess required)
# ---------------------------------------------------------------------------


def test_mcp_request_format() -> None:
    """JSON-RPC requests are properly formatted with incremental IDs."""
    client = McpClient()
    # Poke internal id counter to verify incrementing
    assert client._request_id == 0  # noqa: SLF001

    # Simulate what _send_request would build (without actually sending).
    client._request_id += 1  # noqa: SLF001
    req_id = client._request_id
    message: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/list",
    }
    assert message["jsonrpc"] == "2.0"
    assert message["id"] == 1
    assert message["method"] == "tools/list"

    # Second request increments further.
    client._request_id += 1  # noqa: SLF001
    assert client._request_id == 2  # noqa: SLF001


def test_mcp_request_format_with_params() -> None:
    """JSON-RPC requests include params when provided."""
    message: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "echo", "arguments": {"input": "hi"}},
    }
    encoded = json.dumps(message, separators=(",", ":"))
    decoded = json.loads(encoded)
    assert decoded["params"]["name"] == "echo"


def test_mcp_tool_list_parsing() -> None:
    """Parsing of a tools/list response extracts the tools list."""
    raw_response: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "tools": [
                {
                    "name": "search",
                    "description": "Search the web",
                    "inputSchema": {"type": "object", "properties": {}},
                }
            ]
        },
    }
    tools: list[dict[str, Any]] = raw_response["result"]["tools"]
    assert len(tools) == 1
    assert tools[0]["name"] == "search"


def test_mcp_tool_call_parsing() -> None:
    """Parsing of a tools/call response extracts text content."""
    raw_response: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [
                {"type": "text", "text": "hello "},
                {"type": "text", "text": "world"},
            ]
        },
    }
    content_items: list[dict[str, Any]] = raw_response["result"]["content"]
    texts = [c["text"] for c in content_items if c.get("type") == "text"]
    assert "\n".join(texts) == "hello \nworld"


def test_mcp_error_parsing() -> None:
    """McpError captures code, message, and optional data."""
    err = McpError(code=-32601, message="Method not found", data={"detail": "x"})
    assert err.code == -32601
    assert err.message == "Method not found"
    assert err.data == {"detail": "x"}
    assert "-32601" in str(err)


# ---------------------------------------------------------------------------
# Integration tests — with the mock subprocess server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_lifecycle_with_mock_server() -> None:
    """Start, handshake, and stop with the mock MCP server process."""
    async with McpClient(core_command=_mock_server_command()) as client:
        assert client._server_info.get("serverInfo", {}).get("name") == "mock-core"  # noqa: SLF001


@pytest.mark.asyncio
async def test_list_tools_via_mock_server() -> None:
    """tools/list returns the expected tool from the mock server."""
    async with McpClient(core_command=_mock_server_command()) as client:
        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "echo"
        assert "description" in tools[0]


@pytest.mark.asyncio
async def test_call_tool_via_mock_server() -> None:
    """tools/call returns the echoed text through the mock server."""
    async with McpClient(core_command=_mock_server_command()) as client:
        result = await client.call_tool("echo", {"input": "ping"})
        assert result == "ping"


@pytest.mark.asyncio
async def test_call_unknown_tool_raises() -> None:
    """Calling a non-existent tool raises McpError."""
    async with McpClient(core_command=_mock_server_command()) as client:
        with pytest.raises(McpError, match="Unknown tool"):
            await client.call_tool("nonexistent", {})


@pytest.mark.asyncio
async def test_protocol_version_sent() -> None:
    """The client sends the expected protocol version during init."""
    async with McpClient(core_command=_mock_server_command()) as client:
        assert client._server_info.get("protocolVersion") == _MCP_PROTOCOL_VERSION  # noqa: SLF001


# ---------------------------------------------------------------------------
# McpToolBridge tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_bridge_discover() -> None:
    """McpToolBridge.discover populates available_tools."""
    async with McpClient(core_command=_mock_server_command()) as client:
        bridge = McpToolBridge(client)
        assert bridge.available_tools == []

        tools = await bridge.discover()
        assert len(tools) == 1
        assert bridge.available_tools == tools


@pytest.mark.asyncio
async def test_tool_bridge_execute() -> None:
    """McpToolBridge.execute forwards the call through MCP."""
    async with McpClient(core_command=_mock_server_command()) as client:
        bridge = McpToolBridge(client)
        result = await bridge.execute("echo", {"input": "hello bridge"})
        assert result == "hello bridge"


# ---------------------------------------------------------------------------
# Schema regression tests — keep mock aligned with real ygn-core
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_echo_tool_schema_has_input_parameter() -> None:
    """Regression: echo tool expects 'input' (not 'text') per ygn-core/src/tool.rs.

    The real ygn-core EchoTool uses ``{"input": "..."}`` as its parameter.
    This test ensures the mock server matches and that call_tool works with
    the correct parameter name.
    """
    async with McpClient(core_command=_mock_server_command()) as client:
        tools = await client.list_tools()
        echo = next(t for t in tools if t["name"] == "echo")
        schema = echo["inputSchema"]
        # Must have 'input' property (not 'text')
        assert "input" in schema["properties"], (
            "echo tool schema must use 'input' parameter, not 'text'"
        )
        assert "text" not in schema["properties"], (
            "echo tool schema must NOT have 'text' — the parameter is 'input'"
        )
        assert schema.get("required") == ["input"]

        # Calling with correct parameter works
        result = await client.call_tool("echo", {"input": "regression check"})
        assert result == "regression check"

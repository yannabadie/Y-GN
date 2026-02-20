"""MCP client that communicates with ygn-core via stdio JSON-RPC 2.0."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CORE_COMMAND: list[str] = ["ygn-core", "mcp"]

# MCP protocol version announced during handshake.
_MCP_PROTOCOL_VERSION = "2024-11-05"


class McpError(Exception):
    """Raised when the MCP server returns a JSON-RPC error."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"MCP error {code}: {message}")


class McpClient:
    """MCP client that communicates with ygn-core via stdio.

    The client spawns ygn-core as a subprocess and exchanges newline-delimited
    JSON-RPC 2.0 messages over its stdin/stdout.
    """

    def __init__(self, core_command: list[str] | None = None) -> None:
        """Initialize with the command used to spawn the MCP server.

        Args:
            core_command: The argv list for the MCP server process.
                Defaults to ``["ygn-core", "mcp"]``.
        """
        self._core_command = core_command if core_command is not None else _DEFAULT_CORE_COMMAND
        self._process: asyncio.subprocess.Process | None = None
        self._request_id: int = 0
        self._server_info: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Spawn the MCP server subprocess and perform the initialization handshake."""
        self._process = await asyncio.create_subprocess_exec(
            *self._core_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Step 1: send `initialize` request
        result = await self._send_request(
            "initialize",
            {
                "protocolVersion": _MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "ygn-brain", "version": "0.1.0"},
            },
        )
        self._server_info = result
        logger.info("MCP server initialized: %s", result.get("serverInfo", {}))

        # Step 2: send `notifications/initialized` notification
        await self._send_notification("notifications/initialized")

    async def stop(self) -> None:
        """Stop the MCP server subprocess gracefully."""
        proc = self._process
        if proc is None:
            return

        # Close stdin to signal EOF, then wait briefly for the process.
        if proc.stdin is not None:
            proc.stdin.close()
            # Ignore errors from closing stdin when process already exited.
            try:
                await proc.stdin.wait_closed()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except TimeoutError:
            proc.kill()
            await proc.wait()

        self._process = None

    # ------------------------------------------------------------------
    # JSON-RPC transport
    # ------------------------------------------------------------------

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a JSON-RPC 2.0 request and wait for the matching response.

        Returns:
            The ``result`` field of the response.

        Raises:
            McpError: If the server returns a JSON-RPC error object.
            RuntimeError: If the subprocess is not running.
        """
        self._request_id += 1
        req_id = self._request_id

        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params

        await self._write_message(message)
        response = await self._read_message()

        if "error" in response:
            err = response["error"]
            raise McpError(
                code=err.get("code", -1),
                message=err.get("message", "unknown error"),
                data=err.get("data"),
            )

        return response.get("result", {})  # type: ignore[no-any-return]

    async def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC 2.0 notification (no ``id``, no response expected)."""
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            message["params"] = params

        await self._write_message(message)

    # ------------------------------------------------------------------
    # Low-level I/O helpers
    # ------------------------------------------------------------------

    async def _write_message(self, message: dict[str, Any]) -> None:
        proc = self._process
        if proc is None or proc.stdin is None:
            msg = "MCP subprocess is not running"
            raise RuntimeError(msg)

        line = json.dumps(message, separators=(",", ":")) + "\n"
        proc.stdin.write(line.encode())
        await proc.stdin.drain()

    async def _read_message(self) -> dict[str, Any]:
        proc = self._process
        if proc is None or proc.stdout is None:
            msg = "MCP subprocess is not running"
            raise RuntimeError(msg)

        raw = await proc.stdout.readline()
        if not raw:
            msg = "MCP subprocess closed stdout unexpectedly"
            raise RuntimeError(msg)

        return json.loads(raw)  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # High-level MCP operations
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """Discover available tools from the MCP server.

        Returns:
            A list of tool specification dicts (each has ``name``,
            ``description``, ``inputSchema``, etc.).
        """
        result = await self._send_request("tools/list")
        return result.get("tools", [])  # type: ignore[no-any-return]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the MCP server and return the text result.

        Args:
            name: Tool name as advertised by ``list_tools``.
            arguments: Arguments matching the tool's ``inputSchema``.

        Returns:
            The concatenated text content from the tool response.
        """
        result = await self._send_request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        # MCP responses contain a `content` list; extract text items.
        content_items: list[dict[str, Any]] = result.get("content", [])
        texts = [item["text"] for item in content_items if item.get("type") == "text"]
        return "\n".join(texts)

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> McpClient:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()

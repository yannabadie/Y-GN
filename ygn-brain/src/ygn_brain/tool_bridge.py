"""Bridge between MCP tools and the orchestrator's execution pipeline."""

from __future__ import annotations

from typing import Any

from .mcp_client import McpClient


class McpToolBridge:
    """Bridges MCP tools into the orchestrator's execution pipeline.

    Wraps an :class:`McpClient` to provide a simple discover-then-execute
    workflow that the orchestrator can consume without knowing MCP details.
    """

    def __init__(self, mcp_client: McpClient) -> None:
        self.client = mcp_client
        self._tools: list[dict[str, Any]] = []

    async def discover(self) -> list[dict[str, Any]]:
        """Discover and cache available tools from the MCP server.

        Returns:
            A list of tool specification dicts.
        """
        self._tools = await self.client.list_tools()
        return self._tools

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool via MCP.

        Args:
            tool_name: Name of the tool to invoke.
            arguments: Arguments matching the tool's input schema.

        Returns:
            The text result from the tool.
        """
        return await self.client.call_tool(tool_name, arguments)

    @property
    def available_tools(self) -> list[dict[str, Any]]:
        """Return the cached list of tool specs (populated by :meth:`discover`)."""
        return self._tools

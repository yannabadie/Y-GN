#!/usr/bin/env python3
"""03_mcp_integration.py — Brain-to-Core MCP integration demo.

Demonstrates the full MCP (Model Context Protocol) lifecycle:
  1. Spawn ygn-core as an MCP server subprocess (stdio transport)
  2. Perform the JSON-RPC initialize handshake
  3. Discover available tools
  4. Call the echo tool
  5. Print results

This is a standalone script that shows how the Brain communicates with
the Core over the MCP protocol for tool discovery and execution.

Prerequisites:
    - ygn-core built and on PATH (see INSTALL.md, step 3)
    - ygn-brain installed (see INSTALL.md, step 4)

Usage:
    python examples/03_mcp_integration.py
"""

from __future__ import annotations

import asyncio
import sys

from ygn_brain import McpClient


async def main() -> None:
    # ------------------------------------------------------------------
    # 1. Create an McpClient.
    #    By default it spawns `ygn-core mcp` as a child process and
    #    communicates over stdin/stdout using newline-delimited JSON-RPC 2.0.
    # ------------------------------------------------------------------
    print("=== Y-GN MCP Integration Demo ===")
    print()

    # Use the async context manager which handles start() and stop().
    async with McpClient() as client:
        # --------------------------------------------------------------
        # 2. The handshake has already been completed by McpClient.start():
        #      - Client sends `initialize` with protocolVersion and clientInfo
        #      - Server responds with serverInfo and capabilities
        #      - Client sends `notifications/initialized` notification
        #    At this point, the MCP session is fully established.
        # --------------------------------------------------------------
        print("[OK] MCP session established with ygn-core")
        print()

        # --------------------------------------------------------------
        # 3. Discover available tools.
        #    Sends `tools/list` and receives tool specs with name,
        #    description, and inputSchema for each tool.
        # --------------------------------------------------------------
        tools = await client.list_tools()
        print(f"Available tools ({len(tools)}):")
        for tool in tools:
            schema = tool.get("inputSchema", {})
            params = list(schema.get("properties", {}).keys())
            print(f"  - {tool['name']}: {tool.get('description', 'no description')}")
            print(f"    parameters: {params}")
        print()

        # --------------------------------------------------------------
        # 4. Call the echo tool.
        #    Sends a `tools/call` request with the tool name and arguments.
        #    The Core executes the tool (subject to policy checks) and
        #    returns the result as MCP content items.
        # --------------------------------------------------------------
        echo_input = "Hello from Brain via MCP!"
        print(f"Calling echo tool with: {echo_input!r}")
        reply = await client.call_tool("echo", {"text": echo_input})
        print(f"Echo reply: {reply}")
        print()

    # ------------------------------------------------------------------
    # 5. The context manager has stopped the subprocess.
    # ------------------------------------------------------------------
    print("[OK] MCP session closed")
    print()
    print("=== Done ===")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except FileNotFoundError:
        print(
            "Error: 'ygn-core' not found on PATH.\n"
            "Make sure you have built ygn-core and added it to your PATH.\n"
            "See INSTALL.md, step 3.",
            file=sys.stderr,
        )
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)

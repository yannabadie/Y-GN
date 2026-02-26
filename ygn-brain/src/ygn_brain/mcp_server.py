"""Brain MCP Server — exposes brain tools via JSON-RPC 2.0 over stdio.

Mirrors the ygn-core MCP server protocol (same JSON-RPC format).
Transport: stdio (line-delimited JSON-RPC).
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from .evidence import EvidencePack
from .guard import GuardPipeline
from .memory import InMemoryBackend, MemoryService
from .orchestrator import Orchestrator
from .swarm import SwarmEngine, SwarmMode

# ---------------------------------------------------------------------------
# Tool schemas (MCP tools/list response)
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "name": "orchestrate",
        "description": "Run full HiveMind pipeline",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task to execute"},
                "timeout_sec": {"type": "number", "description": "Timeout in seconds"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "guard_check",
        "description": "Evaluate input against Guard pipeline",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to evaluate"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "evidence_export",
        "description": "Export Evidence Pack as JSONL",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID to export"},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "swarm_execute",
        "description": "Run Swarm with specific mode",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task to execute"},
                "mode": {"type": "string", "description": "Swarm mode (optional)"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "memory_recall",
        "description": "Query 3-tier memory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "tier": {"type": "string", "description": "Memory tier (optional)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_search_semantic",
        "description": "Semantic memory recall using vector embeddings",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results"},
            },
            "required": ["query"],
        },
    },
]

_JSONRPC_PARSE_ERROR = -32700
_JSONRPC_INVALID_REQUEST = -32600
_JSONRPC_METHOD_NOT_FOUND = -32601
_JSONRPC_INTERNAL_ERROR = -32603


def _error_response(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _result_response(req_id: Any, result: Any) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


class McpBrainServer:
    """Brain MCP server — handles JSON-RPC messages."""

    def __init__(
        self,
        orchestrator: Orchestrator | None = None,
        guard_pipeline: GuardPipeline | None = None,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._orchestrator = orchestrator if orchestrator is not None else Orchestrator()
        self._guard = guard_pipeline if guard_pipeline is not None else GuardPipeline()
        self._memory = memory_service if memory_service is not None else InMemoryBackend()
        self._swarm = SwarmEngine()
        self._evidence_store: dict[str, EvidencePack] = {}

    async def handle_message(self, line: str) -> str:
        """Parse JSON-RPC request, route to handler, return JSON-RPC response."""
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return json.dumps(_error_response(None, _JSONRPC_PARSE_ERROR, "Parse error"))

        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params", {})

        if method == "initialize":
            return json.dumps(self._handle_initialize(req_id))
        if method == "tools/list":
            return json.dumps(self._handle_tools_list(req_id))
        if method == "tools/call":
            return json.dumps(await self._handle_tools_call(req_id, params))

        return json.dumps(
            _error_response(req_id, _JSONRPC_METHOD_NOT_FOUND, f"Unknown method: {method}")
        )

    def _handle_initialize(self, req_id: Any) -> dict[str, Any]:
        return _result_response(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": "ygn-brain",
                "version": "0.3.0",
            },
        })

    def _handle_tools_list(self, req_id: Any) -> dict[str, Any]:
        return _result_response(req_id, {"tools": _TOOLS})

    async def _handle_tools_call(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        try:
            if tool_name == "orchestrate":
                return _result_response(req_id, self._call_orchestrate(arguments))
            if tool_name == "guard_check":
                return _result_response(req_id, self._call_guard_check(arguments))
            if tool_name == "evidence_export":
                return _result_response(req_id, self._call_evidence_export(arguments))
            if tool_name == "swarm_execute":
                return _result_response(req_id, self._call_swarm_execute(arguments))
            if tool_name == "memory_recall":
                return _result_response(req_id, self._call_memory_recall(arguments))
            if tool_name == "memory_search_semantic":
                return _result_response(req_id, self._call_memory_search_semantic(arguments))
            return _error_response(req_id, _JSONRPC_METHOD_NOT_FOUND, f"Unknown tool: {tool_name}")
        except Exception as exc:  # noqa: BLE001
            return _error_response(req_id, _JSONRPC_INTERNAL_ERROR, str(exc))

    def _call_orchestrate(self, args: dict[str, Any]) -> dict[str, Any]:
        task = args["task"]
        result = self._orchestrator.run(task)
        session_id = result["session_id"]
        # Store evidence for later export
        self._evidence_store[session_id] = self._orchestrator.evidence
        return {
            "content": [{"type": "text", "text": result.get("result", "")}],
            "session_id": session_id,
            "phases": 7,
        }

    def _call_guard_check(self, args: dict[str, Any]) -> dict[str, Any]:
        text = args["text"]
        result = self._guard.evaluate(text)
        return {
            "content": [{"type": "text", "text": result.reason}],
            "allowed": result.allowed,
            "threat_level": result.threat_level,
            "score": result.score,
            "reason": result.reason,
        }

    def _call_evidence_export(self, args: dict[str, Any]) -> dict[str, Any]:
        session_id = args["session_id"]
        pack = self._evidence_store.get(session_id)
        if pack is None:
            return {
                "content": [{"type": "text", "text": "No evidence found"}],
                "jsonl": "",
                "entry_count": 0,
                "merkle_root": "",
            }
        return {
            "content": [{"type": "text", "text": pack.to_jsonl()}],
            "jsonl": pack.to_jsonl(),
            "entry_count": len(pack.entries),
            "merkle_root": pack.merkle_root_hash(),
        }

    def _call_swarm_execute(self, args: dict[str, Any]) -> dict[str, Any]:
        task = args["task"]
        mode_str = args.get("mode")
        if mode_str:
            try:
                SwarmMode(mode_str)
            except ValueError:
                pass
        result = self._swarm.run(task)
        return {
            "content": [{"type": "text", "text": result.output}],
            "output": result.output,
            "mode": result.mode,
            "metadata": result.metadata,
        }

    def _call_memory_recall(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args["query"]
        entries = self._memory.recall(query, limit=5)
        results = [
            {"key": e.key, "content": e.content, "category": e.category}
            for e in entries
        ]
        return {
            "content": [{"type": "text", "text": json.dumps(results)}],
            "results": results,
            "tier": args.get("tier", "all"),
            "count": len(results),
        }

    def _call_memory_search_semantic(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args.get("query", "")
        limit = args.get("limit", 5)
        # Use regular recall for now (semantic search is available when
        # TieredMemoryService has an embedding_service configured)
        results = self._memory.recall(query, limit=limit)
        entries = [
            {"key": r.key, "content": r.content, "category": r.category.value}
            for r in results
        ]
        mode = (
            "semantic"
            if hasattr(self._memory, "_embedding_service") and self._memory._embedding_service
            else "bm25"
        )
        return {
            "content": [{"type": "text", "text": json.dumps(entries)}],
            "results": entries,
            "count": len(entries),
            "mode": mode,
        }

    async def run_stdio(self) -> None:
        """Read stdin line-by-line, handle, write to stdout."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            line = await reader.readline()
            if not line:
                break
            response = await self.handle_message(line.decode().strip())
            sys.stdout.write(response + "\n")
            sys.stdout.flush()


def main() -> None:
    """Entry point for ygn-brain-mcp CLI."""
    server = McpBrainServer()
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()

"""ToolInterruptHandler — wraps McpToolBridge with event emission + normalization."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ..context_compiler.artifact_store import ArtifactStore
from ..context_compiler.session import Session
from .events import ToolEvent, ToolEventKind
from .normalizer import PerceptionAligner


class ToolInterruptHandler:
    """Wraps a tool bridge with typed events, normalization, and artifact externalization."""

    def __init__(
        self,
        bridge: Any,  # McpToolBridge or any object with async execute(name, args)
        normalizer: PerceptionAligner,
        session: Session,
        artifact_store: ArtifactStore | None = None,
        externalize_threshold: int = 1024,
    ) -> None:
        self._bridge = bridge
        self._normalizer = normalizer
        self._session = session
        self._artifact_store = artifact_store
        self._threshold = externalize_threshold

    async def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_sec: float = 30.0,
    ) -> ToolEvent:
        """Execute a tool with event emission, normalization, and optional externalization."""
        # 1. Emit CALL event
        self._session.record(
            "tool_call",
            {"tool_name": tool_name, "arguments": arguments},
            token_estimate=10,
        )

        start = time.perf_counter()
        try:
            # 2. Execute with timeout
            result = await asyncio.wait_for(
                self._bridge.execute(tool_name, arguments),
                timeout=timeout_sec,
            )
            latency = (time.perf_counter() - start) * 1000

            # 3. Normalize
            normalized = self._normalizer.normalize(tool_name, str(result))

            # 4. Externalize if large
            result_str = str(result)
            if self._artifact_store and len(result_str.encode()) >= self._threshold:
                handle = self._artifact_store.store(
                    result_str.encode(),
                    source=f"tool:{tool_name}",
                )
                self._session.record(
                    "artifact_stored",
                    {"handle": handle.artifact_id, "source": handle.source},
                    token_estimate=10,
                )

            # 5. Emit SUCCESS event
            event = ToolEvent.create(
                kind=ToolEventKind.SUCCESS,
                tool_name=tool_name,
                arguments=arguments,
                result=result_str,
                latency_ms=latency,
                normalized=normalized,
            )
            self._session.record(
                "tool_success",
                {"tool_name": tool_name, "latency_ms": latency},
                token_estimate=5,
            )
            return event

        except TimeoutError:
            latency = (time.perf_counter() - start) * 1000
            event = ToolEvent.create(
                kind=ToolEventKind.TIMEOUT,
                tool_name=tool_name,
                arguments=arguments,
                error=f"Tool '{tool_name}' timed out after {timeout_sec}s",
                latency_ms=latency,
            )
            self._session.record(
                "tool_timeout",
                {"tool_name": tool_name, "timeout_sec": timeout_sec},
                token_estimate=5,
            )
            return event

        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            event = ToolEvent.create(
                kind=ToolEventKind.ERROR,
                tool_name=tool_name,
                arguments=arguments,
                error=str(exc),
                latency_ms=latency,
            )
            self._session.record(
                "tool_error",
                {"tool_name": tool_name, "error": str(exc)},
                token_estimate=5,
            )
            return event

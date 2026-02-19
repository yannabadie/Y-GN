"""OpenTelemetry tracing integration for ygn-brain.

Provides distributed tracing with support for stdout, OTLP, and noop exporters.
"""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import NoOpTracer, Span, Tracer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class TelemetryConfig:
    """Configuration for the ygn-brain tracing subsystem."""

    service_name: str = "ygn-brain"
    enabled: bool = True
    exporter: str = "none"  # "stdout" | "otlp" | "none"
    otlp_endpoint: str = "http://localhost:4317"


# ---------------------------------------------------------------------------
# YgnTracer
# ---------------------------------------------------------------------------


class YgnTracer:
    """Central tracer for ygn-brain.

    Wraps OpenTelemetry ``TracerProvider`` setup and provides helpers for
    creating spans and recording events.
    """

    def __init__(self, config: TelemetryConfig | None = None) -> None:
        self._config = config or TelemetryConfig()
        self._provider: TracerProvider | None = None
        self._tracer: Tracer = NoOpTracer()

    # -- lifecycle -----------------------------------------------------------

    def init(self) -> None:
        """Set up the OTel TracerProvider based on config."""
        cfg = self._config

        if not cfg.enabled or cfg.exporter == "none":
            # NoOp path — no provider needed, default NoOpTracer stays.
            return

        resource = Resource.create({"service.name": cfg.service_name})

        if cfg.exporter == "stdout":
            from opentelemetry.sdk.trace.export import (
                ConsoleSpanExporter,
                SimpleSpanProcessor,
            )

            provider = TracerProvider(resource=resource)
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
            self._provider = provider
            self._tracer = provider.get_tracer(cfg.service_name)

        elif cfg.exporter == "otlp":
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )
                from opentelemetry.sdk.trace.export import SimpleSpanProcessor
            except ImportError:  # pragma: no cover
                # If the OTLP exporter package is not installed, fall back to
                # noop so the application can still start.
                return

            exporter = OTLPSpanExporter(endpoint=cfg.otlp_endpoint, insecure=True)
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(SimpleSpanProcessor(exporter))
            self._provider = provider
            self._tracer = provider.get_tracer(cfg.service_name)

    # -- span helpers --------------------------------------------------------

    @contextlib.contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, str] | None = None,
    ) -> Generator[Span, None, None]:
        """Create a span as a context manager.

        Usage::

            with tracer.span("my-op", {"key": "val"}) as s:
                ...
        """
        otel_tracer = self._tracer
        with otel_tracer.start_as_current_span(name) as s:
            if attributes:
                for k, v in attributes.items():
                    s.set_attribute(k, v)
            yield s

    def record_event(
        self,
        name: str,
        attributes: dict[str, str] | None = None,
    ) -> None:
        """Record a named event on the current active span (if any)."""
        current_span = trace.get_current_span()
        if current_span.is_recording():
            otel_attrs: dict[str, Any] = dict(attributes) if attributes else {}
            current_span.add_event(name, otel_attrs)

    def shutdown(self) -> None:
        """Flush pending spans and shut down the provider.

        Safe to call multiple times.
        """
        if self._provider is not None:
            self._provider.shutdown()
            self._provider = None


# ---------------------------------------------------------------------------
# Module-level singleton (lazily initialised)
# ---------------------------------------------------------------------------

_DEFAULT_TRACER: YgnTracer | None = None


def _get_default_tracer() -> YgnTracer:
    global _DEFAULT_TRACER  # noqa: PLW0603
    if _DEFAULT_TRACER is None:
        _DEFAULT_TRACER = YgnTracer()
    return _DEFAULT_TRACER


# ---------------------------------------------------------------------------
# Convenience context managers
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def trace_orchestrator_run(session_id: str) -> Generator[Span, None, None]:
    """Trace an orchestrator run."""
    with _get_default_tracer().span("orchestrator/run", {"session.id": session_id}) as s:
        yield s


@contextlib.contextmanager
def trace_hivemind_phase(phase: str) -> Generator[Span, None, None]:
    """Trace a HiveMind phase."""
    with _get_default_tracer().span("hivemind/phase", {"hivemind.phase": phase}) as s:
        yield s


@contextlib.contextmanager
def trace_guard_check(threat_level: str) -> Generator[Span, None, None]:
    """Trace a guard check."""
    with _get_default_tracer().span("guard/check", {"guard.threat_level": threat_level}) as s:
        yield s


@contextlib.contextmanager
def trace_mcp_call(tool_name: str) -> Generator[Span, None, None]:
    """Trace an MCP tool call."""
    with _get_default_tracer().span("mcp/call", {"mcp.tool": tool_name}) as s:
        yield s

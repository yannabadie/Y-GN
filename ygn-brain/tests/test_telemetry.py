"""Tests for telemetry module — OpenTelemetry tracing integration."""

from __future__ import annotations

from ygn_brain.telemetry import (
    TelemetryConfig,
    YgnTracer,
    trace_guard_check,
    trace_hivemind_phase,
    trace_mcp_call,
    trace_orchestrator_run,
)


def test_init_with_none_config_succeeds() -> None:
    config = TelemetryConfig(exporter="none")
    tracer = YgnTracer(config)
    tracer.init()
    tracer.shutdown()


def test_span_context_manager_works() -> None:
    config = TelemetryConfig(exporter="none")
    tracer = YgnTracer(config)
    tracer.init()
    with tracer.span("test-span", {"key": "value"}) as s:
        assert s is not None
    tracer.shutdown()


def test_record_event_does_not_error() -> None:
    config = TelemetryConfig(exporter="none")
    tracer = YgnTracer(config)
    tracer.init()
    tracer.record_event("test-event", {"key": "value"})
    tracer.shutdown()


def test_convenience_functions_do_not_error() -> None:
    with trace_orchestrator_run("session-1") as s:
        assert s is not None
    with trace_hivemind_phase("analyse") as s:
        assert s is not None
    with trace_guard_check("low") as s:
        assert s is not None
    with trace_mcp_call("echo") as s:
        assert s is not None


def test_config_defaults_are_correct() -> None:
    config = TelemetryConfig()
    assert config.service_name == "ygn-brain"
    assert config.enabled is True
    assert config.exporter == "none"
    assert config.otlp_endpoint == "http://localhost:4317"


def test_shutdown_is_safe_to_call_multiple_times() -> None:
    config = TelemetryConfig(exporter="none")
    tracer = YgnTracer(config)
    tracer.init()
    tracer.shutdown()
    tracer.shutdown()  # second call should not raise
    tracer.shutdown()  # third call should not raise

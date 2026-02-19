//! OpenTelemetry tracing integration for ygn-core.
//!
//! Provides structured distributed tracing via OpenTelemetry, with support
//! for Stdout, OTLP, and Noop exporters.

use opentelemetry::global::BoxedSpan;
use opentelemetry::trace::{self, Span, Status, Tracer, TracerProvider};
use opentelemetry::KeyValue;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Configuration types
// ---------------------------------------------------------------------------

/// Exporter backend for trace data.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum ExporterType {
    /// Print spans to stdout (useful for development).
    Stdout,
    /// Send spans via OTLP (HTTP or gRPC).
    Otlp,
    /// Discard all spans (noop).
    None,
}

/// Configuration for the tracing subsystem.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TracingConfig {
    /// Service name reported in traces.
    #[serde(default = "default_service_name")]
    pub service_name: String,
    /// Whether tracing is enabled at all.
    #[serde(default = "default_enabled")]
    pub enabled: bool,
    /// Which exporter backend to use.
    #[serde(default = "default_exporter")]
    pub exporter: ExporterType,
    /// Endpoint for the OTLP exporter (ignored for other exporters).
    #[serde(default)]
    pub otlp_endpoint: Option<String>,
}

fn default_service_name() -> String {
    "ygn-core".to_string()
}

fn default_enabled() -> bool {
    true
}

fn default_exporter() -> ExporterType {
    ExporterType::None
}

impl Default for TracingConfig {
    fn default() -> Self {
        Self {
            service_name: default_service_name(),
            enabled: default_enabled(),
            exporter: default_exporter(),
            otlp_endpoint: None,
        }
    }
}

// ---------------------------------------------------------------------------
// SpanGuard — inner enum to support both SDK and boxed span types
// ---------------------------------------------------------------------------

/// Internal enum so `SpanGuard` can hold either the concrete SDK span
/// (returned by `SdkTracerProvider`) or the type-erased global `BoxedSpan`.
enum InnerSpan {
    Sdk(Box<opentelemetry_sdk::trace::Span>),
    Boxed(BoxedSpan),
}

impl InnerSpan {
    fn set_attribute_kv(&mut self, kv: KeyValue) {
        match self {
            InnerSpan::Sdk(s) => s.set_attribute(kv),
            InnerSpan::Boxed(s) => s.set_attribute(kv),
        }
    }

    fn set_status_inner(&mut self, status: Status) {
        match self {
            InnerSpan::Sdk(s) => s.set_status(status),
            InnerSpan::Boxed(s) => s.set_status(status),
        }
    }

    fn end_inner(&mut self) {
        match self {
            InnerSpan::Sdk(s) => s.end(),
            InnerSpan::Boxed(s) => s.end(),
        }
    }
}

// ---------------------------------------------------------------------------
// SpanGuard
// ---------------------------------------------------------------------------

/// RAII guard that wraps an OpenTelemetry span.
///
/// The underlying span is automatically ended when the guard is dropped.
pub struct SpanGuard {
    inner: InnerSpan,
}

impl SpanGuard {
    /// Set an attribute on the wrapped span.
    pub fn set_attribute(&mut self, key: &str, value: String) {
        self.inner
            .set_attribute_kv(KeyValue::new(key.to_owned(), value));
    }

    /// Set the span status to Ok or Error.
    pub fn set_status(&mut self, success: bool, message: &str) {
        if success {
            self.inner.set_status_inner(Status::Ok);
        } else {
            self.inner
                .set_status_inner(Status::error(message.to_owned()));
        }
    }
}

impl Drop for SpanGuard {
    fn drop(&mut self) {
        self.inner.end_inner();
    }
}

// ---------------------------------------------------------------------------
// YgnTracer
// ---------------------------------------------------------------------------

/// Central tracer for ygn-core.
///
/// Holds onto the [`SdkTracerProvider`] so it can be shut down cleanly, and
/// vends [`SpanGuard`]s for structured tracing.
pub struct YgnTracer {
    provider: opentelemetry_sdk::trace::SdkTracerProvider,
    service_name: String,
    /// Whether tracing is enabled. When `false`, spans are still created
    /// (noop cost) but callers can check this flag to skip expensive
    /// attribute-building work.
    pub enabled: bool,
}

impl YgnTracer {
    /// Initialise the OpenTelemetry tracing pipeline.
    ///
    /// # Errors
    /// Returns an error if the OTLP exporter cannot be configured.
    pub fn init(config: &TracingConfig) -> anyhow::Result<Self> {
        let provider = match config.exporter {
            ExporterType::None => opentelemetry_sdk::trace::SdkTracerProvider::builder().build(),
            ExporterType::Stdout => {
                // For Stdout we use a default provider; actual stdout logging
                // is handled by the `tracing` crate already configured in the
                // gateway.  This keeps the Stdout path simple and avoids
                // pulling in an extra stdout span exporter dependency.
                opentelemetry_sdk::trace::SdkTracerProvider::builder().build()
            }
            ExporterType::Otlp => {
                // Build an OTLP HTTP exporter. At construction time this does
                // NOT attempt to connect — the first export call will.
                let mut builder = opentelemetry_otlp::SpanExporter::builder().with_http();

                if let Some(ref endpoint) = config.otlp_endpoint {
                    use opentelemetry_otlp::HasExportConfig;
                    builder.export_config().endpoint = Some(endpoint.clone());
                }

                let exporter = builder.build()?;

                opentelemetry_sdk::trace::SdkTracerProvider::builder()
                    .with_simple_exporter(exporter)
                    .build()
            }
        };

        Ok(Self {
            provider,
            service_name: config.service_name.clone(),
            enabled: config.enabled,
        })
    }

    /// Create a new span with the given name.
    pub fn span(&self, name: &str) -> SpanGuard {
        let tracer = self.provider.tracer(self.service_name.clone());
        let span = tracer.start(name.to_owned());
        SpanGuard {
            inner: InnerSpan::Sdk(Box::new(span)),
        }
    }

    /// Record a named event with attributes on the current active span (if any).
    pub fn record_event(&self, name: &str, attributes: &[(&str, String)]) {
        trace::get_active_span(|span| {
            let kvs: Vec<KeyValue> = attributes
                .iter()
                .map(|(k, v)| KeyValue::new(k.to_string(), v.clone()))
                .collect();
            span.add_event(name.to_owned(), kvs);
        });
    }

    /// Flush pending spans and shut down the tracing pipeline.
    pub fn shutdown(&self) {
        let _ = self.provider.shutdown();
    }
}

// ---------------------------------------------------------------------------
// Convenience functions
// ---------------------------------------------------------------------------

/// Create a span for a tool call.
pub fn trace_tool_call(tool_name: &str, args: &str) -> SpanGuard {
    let tracer = opentelemetry::global::tracer("ygn-core");
    let mut span = tracer.start(format!("tool_call/{tool_name}"));
    span.set_attribute(KeyValue::new("tool.name", tool_name.to_owned()));
    span.set_attribute(KeyValue::new("tool.args", args.to_owned()));
    SpanGuard {
        inner: InnerSpan::Boxed(span),
    }
}

/// Create a span for an MCP request.
pub fn trace_mcp_request(method: &str) -> SpanGuard {
    let tracer = opentelemetry::global::tracer("ygn-core");
    let mut span = tracer.start(format!("mcp/{method}"));
    span.set_attribute(KeyValue::new("mcp.method", method.to_owned()));
    SpanGuard {
        inner: InnerSpan::Boxed(span),
    }
}

/// Create a span for a policy check.
pub fn trace_policy_check(tool_name: &str, decision: &str) -> SpanGuard {
    let tracer = opentelemetry::global::tracer("ygn-core");
    let mut span = tracer.start(format!("policy_check/{tool_name}"));
    span.set_attribute(KeyValue::new("policy.tool", tool_name.to_owned()));
    span.set_attribute(KeyValue::new("policy.decision", decision.to_owned()));
    SpanGuard {
        inner: InnerSpan::Boxed(span),
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn init_with_none_config_succeeds() {
        let config = TracingConfig {
            exporter: ExporterType::None,
            ..Default::default()
        };
        let tracer = YgnTracer::init(&config).expect("init should succeed");
        tracer.shutdown();
    }

    #[test]
    fn init_with_stdout_config_succeeds() {
        let config = TracingConfig {
            exporter: ExporterType::Stdout,
            ..Default::default()
        };
        let tracer = YgnTracer::init(&config).expect("init should succeed");
        tracer.shutdown();
    }

    #[test]
    fn span_creation_and_drop() {
        let config = TracingConfig {
            exporter: ExporterType::None,
            ..Default::default()
        };
        let tracer = YgnTracer::init(&config).expect("init should succeed");
        {
            let mut guard = tracer.span("test-span");
            guard.set_attribute("key", "value".to_string());
            guard.set_status(true, "");
            // guard dropped here — span ends
        }
        tracer.shutdown();
    }

    #[test]
    fn record_event_does_not_panic() {
        let config = TracingConfig {
            exporter: ExporterType::None,
            ..Default::default()
        };
        let tracer = YgnTracer::init(&config).expect("init should succeed");
        tracer.record_event("test-event", &[("key", "value".to_string())]);
        tracer.shutdown();
    }

    #[test]
    fn tracing_config_serialization() {
        let config = TracingConfig::default();
        let json = serde_json::to_string(&config).expect("serialize should succeed");
        assert!(json.contains("ygn-core"));
        assert!(json.contains("none"));

        let parsed: TracingConfig =
            serde_json::from_str(&json).expect("deserialize should succeed");
        assert_eq!(parsed.service_name, "ygn-core");
        assert_eq!(parsed.exporter, ExporterType::None);
        assert!(parsed.enabled);
    }

    #[test]
    fn convenience_functions_create_spans_without_panic() {
        // These use the global noop tracer (no provider installed) and should
        // never panic.
        {
            let mut guard = trace_tool_call("echo", "{}");
            guard.set_status(true, "ok");
        }
        {
            let _guard = trace_mcp_request("tools/list");
        }
        {
            let _guard = trace_policy_check("rm", "deny");
        }
    }
}

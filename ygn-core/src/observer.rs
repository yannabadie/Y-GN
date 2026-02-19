//! Observability trait and types.
//!
//! Defines the interface for observability backends based on
//! ZeroClaw's Observer trait architecture.

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Events that can be recorded by an observer.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ObserverEvent {
    AgentStart {
        agent_id: String,
        timestamp: DateTime<Utc>,
    },
    LlmRequest {
        provider: String,
        model: String,
        timestamp: DateTime<Utc>,
    },
    LlmResponse {
        provider: String,
        model: String,
        latency_ms: u64,
        timestamp: DateTime<Utc>,
    },
    ToolCallStart {
        tool_name: String,
        timestamp: DateTime<Utc>,
    },
    ToolCall {
        tool_name: String,
        success: bool,
        latency_ms: u64,
        timestamp: DateTime<Utc>,
    },
    Error {
        message: String,
        timestamp: DateTime<Utc>,
    },
}

/// Metrics that can be recorded by an observer.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ObserverMetric {
    RequestLatency { provider: String, latency_ms: f64 },
    TokensUsed { provider: String, tokens: u64 },
    ActiveSessions { count: u64 },
}

// ---------------------------------------------------------------------------
// Trait
// ---------------------------------------------------------------------------

/// Core trait every observability backend must implement.
#[async_trait]
pub trait Observer: Send + Sync {
    /// Human-readable name of this observer.
    fn name(&self) -> &str;

    /// Record a structured event.
    async fn record_event(&self, event: ObserverEvent) -> anyhow::Result<()>;

    /// Record a metric data point.
    async fn record_metric(&self, metric: ObserverMetric) -> anyhow::Result<()>;

    /// Flush any buffered data.
    async fn flush(&self) -> anyhow::Result<()>;
}

// ---------------------------------------------------------------------------
// VerboseObserver (prints to stderr)
// ---------------------------------------------------------------------------

/// An observer that prints all events and metrics to stderr.
/// Useful for local development and debugging.
#[derive(Debug, Clone, Default)]
pub struct VerboseObserver;

#[async_trait]
impl Observer for VerboseObserver {
    fn name(&self) -> &str {
        "verbose"
    }

    async fn record_event(&self, event: ObserverEvent) -> anyhow::Result<()> {
        eprintln!("[observer:verbose] event: {:?}", event);
        Ok(())
    }

    async fn record_metric(&self, metric: ObserverMetric) -> anyhow::Result<()> {
        eprintln!("[observer:verbose] metric: {:?}", metric);
        Ok(())
    }

    async fn flush(&self) -> anyhow::Result<()> {
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// NoopObserver
// ---------------------------------------------------------------------------

/// An observer that silently discards all events and metrics.
#[derive(Debug, Clone, Default)]
pub struct NoopObserver;

#[async_trait]
impl Observer for NoopObserver {
    fn name(&self) -> &str {
        "noop"
    }

    async fn record_event(&self, _event: ObserverEvent) -> anyhow::Result<()> {
        Ok(())
    }

    async fn record_metric(&self, _metric: ObserverMetric) -> anyhow::Result<()> {
        Ok(())
    }

    async fn flush(&self) -> anyhow::Result<()> {
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn noop_observer_records_event() {
        let obs = NoopObserver;
        let event = ObserverEvent::AgentStart {
            agent_id: "test".to_string(),
            timestamp: Utc::now(),
        };
        obs.record_event(event).await.unwrap();
    }

    #[tokio::test]
    async fn noop_observer_records_metric() {
        let obs = NoopObserver;
        let metric = ObserverMetric::ActiveSessions { count: 42 };
        obs.record_metric(metric).await.unwrap();
    }

    #[tokio::test]
    async fn noop_observer_flush() {
        let obs = NoopObserver;
        obs.flush().await.unwrap();
    }

    #[tokio::test]
    async fn verbose_observer_records_event() {
        let obs = VerboseObserver;
        let event = ObserverEvent::Error {
            message: "test error".to_string(),
            timestamp: Utc::now(),
        };
        // Should not error even though it prints to stderr
        obs.record_event(event).await.unwrap();
    }

    #[tokio::test]
    async fn verbose_observer_records_metric() {
        let obs = VerboseObserver;
        let metric = ObserverMetric::RequestLatency {
            provider: "test".to_string(),
            latency_ms: 123.4,
        };
        obs.record_metric(metric).await.unwrap();
    }

    #[test]
    fn observer_names() {
        assert_eq!(VerboseObserver.name(), "verbose");
        assert_eq!(NoopObserver.name(), "noop");
    }

    #[test]
    fn observer_event_serialization() {
        let event = ObserverEvent::ToolCall {
            tool_name: "echo".to_string(),
            success: true,
            latency_ms: 10,
            timestamp: Utc::now(),
        };
        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains("echo"));
    }
}

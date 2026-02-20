//! Provider health tracking and circuit breaker.
//!
//! Records success/failure of LLM provider calls and exposes a simple
//! circuit-breaker that disables providers with too many consecutive
//! failures.

use std::collections::HashMap;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Health status for a single LLM provider.
#[derive(Debug, Clone)]
pub struct HealthStatus {
    pub provider: String,
    pub healthy: bool,
    pub last_success: Option<chrono::DateTime<chrono::Utc>>,
    pub last_failure: Option<chrono::DateTime<chrono::Utc>>,
    pub consecutive_failures: u32,
    pub total_requests: u64,
    pub total_failures: u64,
    /// Running average latency in milliseconds.
    pub avg_latency_ms: f64,
}

impl HealthStatus {
    fn new(provider: &str) -> Self {
        Self {
            provider: provider.to_string(),
            healthy: true,
            last_success: None,
            last_failure: None,
            consecutive_failures: 0,
            total_requests: 0,
            total_failures: 0,
            avg_latency_ms: 0.0,
        }
    }
}

// ---------------------------------------------------------------------------
// ProviderHealth
// ---------------------------------------------------------------------------

/// Tracks health status of LLM providers.
pub struct ProviderHealth {
    statuses: HashMap<String, HealthStatus>,
}

impl ProviderHealth {
    /// Create an empty tracker.
    pub fn new() -> Self {
        Self {
            statuses: HashMap::new(),
        }
    }

    /// Record a successful call to the given provider.
    pub fn record_success(&mut self, provider: &str, latency_ms: f64) {
        let status = self
            .statuses
            .entry(provider.to_string())
            .or_insert_with(|| HealthStatus::new(provider));

        status.total_requests += 1;
        status.consecutive_failures = 0;
        status.healthy = true;
        status.last_success = Some(chrono::Utc::now());

        // Incremental average: avg = avg + (new - avg) / n
        let n = (status.total_requests - status.total_failures) as f64;
        if n > 0.0 {
            status.avg_latency_ms += (latency_ms - status.avg_latency_ms) / n;
        }
    }

    /// Record a failed call to the given provider.
    pub fn record_failure(&mut self, provider: &str, _error_msg: &str) {
        let status = self
            .statuses
            .entry(provider.to_string())
            .or_insert_with(|| HealthStatus::new(provider));

        status.total_requests += 1;
        status.total_failures += 1;
        status.consecutive_failures += 1;
        status.last_failure = Some(chrono::Utc::now());

        if status.consecutive_failures >= 5 {
            status.healthy = false;
        }
    }

    /// Returns `true` if the provider is healthy (fewer than 5 consecutive
    /// failures). An unknown provider is considered healthy.
    pub fn is_healthy(&self, provider: &str) -> bool {
        self.statuses
            .get(provider)
            .map(|s| s.consecutive_failures < 5)
            .unwrap_or(true)
    }

    /// Get the full health status for a provider, if tracked.
    pub fn get_status(&self, provider: &str) -> Option<&HealthStatus> {
        self.statuses.get(provider)
    }

    /// List all tracked provider statuses.
    pub fn all_statuses(&self) -> Vec<&HealthStatus> {
        self.statuses.values().collect()
    }

    /// Circuit breaker: returns `true` if the provider should be skipped.
    ///
    /// A provider trips the breaker when it has more than 5 consecutive
    /// failures AND the last failure was within the last 5 minutes.
    pub fn circuit_breaker(&self, provider: &str) -> bool {
        let status = match self.statuses.get(provider) {
            Some(s) => s,
            None => return false, // unknown provider — not tripped
        };

        if status.consecutive_failures <= 5 {
            return false;
        }

        // Check recency of last failure
        if let Some(last_fail) = status.last_failure {
            let elapsed = chrono::Utc::now() - last_fail;
            elapsed < chrono::Duration::minutes(5)
        } else {
            false
        }
    }
}

impl Default for ProviderHealth {
    fn default() -> Self {
        Self::new()
    }
}

impl std::fmt::Debug for ProviderHealth {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ProviderHealth")
            .field("providers", &self.statuses.keys().collect::<Vec<_>>())
            .finish()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_success_updates_stats() {
        let mut health = ProviderHealth::new();
        health.record_success("claude", 150.0);

        let status = health.get_status("claude").unwrap();
        assert_eq!(status.total_requests, 1);
        assert_eq!(status.total_failures, 0);
        assert!(status.last_success.is_some());
        assert!(status.healthy);
    }

    #[test]
    fn record_failure_increments_counter() {
        let mut health = ProviderHealth::new();
        health.record_failure("openai", "timeout");

        let status = health.get_status("openai").unwrap();
        assert_eq!(status.consecutive_failures, 1);
        assert_eq!(status.total_failures, 1);
        assert_eq!(status.total_requests, 1);
        assert!(status.last_failure.is_some());
    }

    #[test]
    fn is_healthy_returns_false_after_five_failures() {
        let mut health = ProviderHealth::new();
        for _ in 0..4 {
            health.record_failure("bad", "error");
        }
        assert!(health.is_healthy("bad"));

        health.record_failure("bad", "error"); // 5th failure
        assert!(!health.is_healthy("bad"));
    }

    #[test]
    fn circuit_breaker_triggers_correctly() {
        let mut health = ProviderHealth::new();
        // Need > 5 consecutive failures
        for _ in 0..6 {
            health.record_failure("flaky", "error");
        }

        // Last failure is fresh — breaker should be open
        assert!(health.circuit_breaker("flaky"));
    }

    #[test]
    fn circuit_breaker_not_tripped_for_unknown_provider() {
        let health = ProviderHealth::new();
        assert!(!health.circuit_breaker("unknown"));
    }

    #[test]
    fn avg_latency_computed_correctly() {
        let mut health = ProviderHealth::new();
        health.record_success("claude", 100.0);
        health.record_success("claude", 200.0);
        health.record_success("claude", 300.0);

        let status = health.get_status("claude").unwrap();
        // Average of 100, 200, 300 = 200
        assert!((status.avg_latency_ms - 200.0).abs() < 1.0);
    }

    #[test]
    fn get_status_returns_none_for_unknown_provider() {
        let health = ProviderHealth::new();
        assert!(health.get_status("nonexistent").is_none());
    }

    #[test]
    fn consecutive_failures_reset_on_success() {
        let mut health = ProviderHealth::new();
        health.record_failure("claude", "timeout");
        health.record_failure("claude", "timeout");
        health.record_failure("claude", "timeout");
        assert_eq!(health.get_status("claude").unwrap().consecutive_failures, 3);

        health.record_success("claude", 100.0);
        assert_eq!(health.get_status("claude").unwrap().consecutive_failures, 0);
        assert!(health.is_healthy("claude"));
    }

    #[test]
    fn all_statuses_lists_all_tracked_providers() {
        let mut health = ProviderHealth::new();
        health.record_success("claude", 100.0);
        health.record_success("openai", 200.0);
        health.record_failure("gemini", "error");

        let statuses = health.all_statuses();
        assert_eq!(statuses.len(), 3);

        let mut names: Vec<&str> = statuses.iter().map(|s| s.provider.as_str()).collect();
        names.sort();
        assert_eq!(names, vec!["claude", "gemini", "openai"]);
    }

    #[test]
    fn healthy_after_recovery() {
        let mut health = ProviderHealth::new();
        // Push past the threshold
        for _ in 0..6 {
            health.record_failure("claude", "error");
        }
        assert!(!health.is_healthy("claude"));

        // A single success should recover
        health.record_success("claude", 100.0);
        assert!(health.is_healthy("claude"));
        assert!(!health.circuit_breaker("claude"));
    }
}

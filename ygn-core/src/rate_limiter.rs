//! Token-bucket rate limiter for LLM API calls.
//!
//! Each provider has its own bucket with configurable rate and burst
//! capacity. No external crates — pure hand-rolled token bucket.

use std::collections::HashMap;
use std::fmt;
use std::time::{Duration, Instant};

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

/// Returned when a rate-limit check fails.
#[derive(Debug, Clone)]
pub struct RateLimitError {
    pub provider: String,
    pub retry_after: Duration,
}

impl fmt::Display for RateLimitError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "rate limited for provider '{}': retry after {:.1}s",
            self.provider,
            self.retry_after.as_secs_f64()
        )
    }
}

impl std::error::Error for RateLimitError {}

// ---------------------------------------------------------------------------
// TokenBucket
// ---------------------------------------------------------------------------

/// A single token bucket with refill mechanics.
#[derive(Debug)]
pub struct TokenBucket {
    /// Maximum tokens (burst capacity).
    capacity: u32,
    /// Current available tokens (fractional during refill).
    available: f64,
    /// Tokens added per second.
    rate: f64,
    /// Last time tokens were refilled.
    last_refill: Instant,
}

impl TokenBucket {
    /// Create a new bucket filled to capacity.
    fn new(rate: f64, capacity: u32) -> Self {
        Self {
            capacity,
            available: capacity as f64,
            rate,
            last_refill: Instant::now(),
        }
    }

    /// Refill tokens based on elapsed time since last refill.
    fn refill(&mut self) {
        let now = Instant::now();
        let elapsed = now.duration_since(self.last_refill).as_secs_f64();
        if elapsed > 0.0 {
            self.available = (self.available + elapsed * self.rate).min(self.capacity as f64);
            self.last_refill = now;
        }
    }

    /// Try to consume one token. Returns Ok(()) or the duration to wait.
    fn try_acquire(&mut self) -> Result<(), Duration> {
        self.refill();
        if self.available >= 1.0 {
            self.available -= 1.0;
            Ok(())
        } else {
            // How long until one token is available?
            let deficit = 1.0 - self.available;
            let wait_secs = deficit / self.rate;
            Err(Duration::from_secs_f64(wait_secs))
        }
    }

    /// Remaining whole tokens.
    fn remaining(&mut self) -> u32 {
        self.refill();
        self.available as u32
    }

    /// Reset to full capacity.
    fn reset(&mut self) {
        self.available = self.capacity as f64;
        self.last_refill = Instant::now();
    }
}

// ---------------------------------------------------------------------------
// RateLimiter
// ---------------------------------------------------------------------------

/// Token-bucket rate limiter for API calls.
/// Each provider has its own bucket with configurable rate and burst.
pub struct RateLimiter {
    buckets: HashMap<String, TokenBucket>,
}

impl RateLimiter {
    /// Create an empty rate limiter with no provider buckets.
    pub fn new() -> Self {
        Self {
            buckets: HashMap::new(),
        }
    }

    /// Create a rate limiter pre-configured with sensible defaults:
    /// - claude:  60 req/min (1.0/s, burst 10)
    /// - openai:  60 req/min (1.0/s, burst 10)
    /// - gemini:  60 req/min (1.0/s, burst 10)
    /// - ollama: 120 req/min (2.0/s, burst 20)
    pub fn with_defaults() -> Self {
        let mut limiter = Self::new();
        limiter.configure("claude", 1.0, 10);
        limiter.configure("openai", 1.0, 10);
        limiter.configure("gemini", 1.0, 10);
        limiter.configure("ollama", 2.0, 20);
        limiter
    }

    /// Configure (or reconfigure) the rate for a provider.
    pub fn configure(&mut self, provider: &str, rate_per_sec: f64, burst: u32) {
        self.buckets
            .insert(provider.to_string(), TokenBucket::new(rate_per_sec, burst));
    }

    /// Try to consume one token for the given provider.
    /// Returns `Ok(())` if the token was acquired, or a `RateLimitError`
    /// indicating how long to wait.
    pub fn try_acquire(&mut self, provider: &str) -> Result<(), RateLimitError> {
        let bucket = self
            .buckets
            .get_mut(provider)
            .ok_or_else(|| RateLimitError {
                provider: provider.to_string(),
                retry_after: Duration::ZERO,
            })?;

        bucket.try_acquire().map_err(|wait| RateLimitError {
            provider: provider.to_string(),
            retry_after: wait,
        })
    }

    /// Calculate how long to wait before a token is available, then
    /// logically consume the token. Returns the `Duration` the caller
    /// should sleep (zero if a token was immediately available).
    ///
    /// For async callers: `tokio::time::sleep(limiter.wait_and_acquire(provider))`.
    pub fn wait_and_acquire(&mut self, provider: &str) -> Duration {
        let bucket = match self.buckets.get_mut(provider) {
            Some(b) => b,
            None => return Duration::ZERO,
        };

        bucket.refill();
        if bucket.available >= 1.0 {
            bucket.available -= 1.0;
            Duration::ZERO
        } else {
            let deficit = 1.0 - bucket.available;
            let wait_secs = deficit / bucket.rate;
            // Consume the token optimistically — caller will sleep first.
            bucket.available = 0.0;
            // Advance last_refill so future refills don't double-count.
            bucket.last_refill = Instant::now();
            Duration::from_secs_f64(wait_secs)
        }
    }

    /// How many whole tokens remain for a provider (0 if unknown provider).
    pub fn remaining(&mut self, provider: &str) -> u32 {
        self.buckets
            .get_mut(provider)
            .map(|b| b.remaining())
            .unwrap_or(0)
    }

    /// Reset a provider's bucket to full capacity.
    pub fn reset(&mut self, provider: &str) {
        if let Some(bucket) = self.buckets.get_mut(provider) {
            bucket.reset();
        }
    }
}

impl Default for RateLimiter {
    fn default() -> Self {
        Self::new()
    }
}

impl fmt::Debug for RateLimiter {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("RateLimiter")
            .field("providers", &self.buckets.keys().collect::<Vec<_>>())
            .finish()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;

    #[test]
    fn try_acquire_succeeds_when_tokens_available() {
        let mut limiter = RateLimiter::new();
        limiter.configure("test", 10.0, 5);
        assert!(limiter.try_acquire("test").is_ok());
    }

    #[test]
    fn try_acquire_fails_when_bucket_empty() {
        let mut limiter = RateLimiter::new();
        limiter.configure("test", 1.0, 2);

        // Drain all tokens
        assert!(limiter.try_acquire("test").is_ok());
        assert!(limiter.try_acquire("test").is_ok());

        // Third call should fail
        let err = limiter.try_acquire("test").unwrap_err();
        assert_eq!(err.provider, "test");
        assert!(err.retry_after > Duration::ZERO);
    }

    #[test]
    fn tokens_refill_over_time() {
        let mut limiter = RateLimiter::new();
        limiter.configure("test", 100.0, 5); // 100 tokens/sec

        // Drain all tokens
        for _ in 0..5 {
            limiter.try_acquire("test").unwrap();
        }
        assert!(limiter.try_acquire("test").is_err());

        // Wait for refill (at 100/s, 50ms should give ~5 tokens)
        thread::sleep(Duration::from_millis(60));

        // Should have tokens again
        assert!(limiter.try_acquire("test").is_ok());
    }

    #[test]
    fn configure_custom_rate() {
        let mut limiter = RateLimiter::new();
        limiter.configure("custom", 5.0, 3);

        // Should be able to burst 3
        assert!(limiter.try_acquire("custom").is_ok());
        assert!(limiter.try_acquire("custom").is_ok());
        assert!(limiter.try_acquire("custom").is_ok());

        // Fourth should fail
        assert!(limiter.try_acquire("custom").is_err());
    }

    #[test]
    fn with_defaults_has_all_four_providers() {
        let mut limiter = RateLimiter::with_defaults();
        assert!(limiter.try_acquire("claude").is_ok());
        assert!(limiter.try_acquire("openai").is_ok());
        assert!(limiter.try_acquire("gemini").is_ok());
        assert!(limiter.try_acquire("ollama").is_ok());
    }

    #[test]
    fn remaining_returns_correct_count() {
        let mut limiter = RateLimiter::new();
        limiter.configure("test", 1.0, 5);
        assert_eq!(limiter.remaining("test"), 5);

        limiter.try_acquire("test").unwrap();
        assert_eq!(limiter.remaining("test"), 4);
    }

    #[test]
    fn reset_refills_bucket() {
        let mut limiter = RateLimiter::new();
        limiter.configure("test", 1.0, 5);

        // Drain
        for _ in 0..5 {
            limiter.try_acquire("test").unwrap();
        }
        assert_eq!(limiter.remaining("test"), 0);

        // Reset
        limiter.reset("test");
        assert_eq!(limiter.remaining("test"), 5);
    }

    #[test]
    fn burst_allows_short_bursts() {
        let mut limiter = RateLimiter::new();
        // Low rate but high burst — should allow a burst of requests.
        limiter.configure("burst", 0.1, 10);

        // Should be able to fire 10 requests in rapid succession
        for i in 0..10 {
            assert!(
                limiter.try_acquire("burst").is_ok(),
                "burst request {} failed",
                i
            );
        }

        // 11th should fail
        assert!(limiter.try_acquire("burst").is_err());
    }

    #[test]
    fn unknown_provider_try_acquire_returns_error() {
        let mut limiter = RateLimiter::new();
        let err = limiter.try_acquire("unknown").unwrap_err();
        assert_eq!(err.provider, "unknown");
    }

    #[test]
    fn wait_and_acquire_returns_zero_when_available() {
        let mut limiter = RateLimiter::new();
        limiter.configure("test", 1.0, 5);
        let wait = limiter.wait_and_acquire("test");
        assert_eq!(wait, Duration::ZERO);
    }

    #[test]
    fn wait_and_acquire_returns_positive_when_empty() {
        let mut limiter = RateLimiter::new();
        limiter.configure("test", 1.0, 1);

        // Drain
        limiter.try_acquire("test").unwrap();

        // Now wait_and_acquire should return a positive duration
        let wait = limiter.wait_and_acquire("test");
        assert!(wait > Duration::ZERO);
    }
}

//! Channel trait and types.
//!
//! Defines the interface for message channels (CLI, Telegram, Discord, etc.)
//! based on ZeroClaw's Channel trait architecture.

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// An inbound message received from a channel.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChannelMessage {
    pub channel: String,
    pub sender: String,
    pub content: String,
    pub timestamp: DateTime<Utc>,
    pub metadata: serde_json::Value,
}

/// An outbound message to be sent through a channel.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SendMessage {
    pub content: String,
    pub recipient: Option<String>,
    pub metadata: serde_json::Value,
}

// ---------------------------------------------------------------------------
// Trait
// ---------------------------------------------------------------------------

/// Core trait every message channel must implement.
#[async_trait]
pub trait Channel: Send + Sync {
    /// Human-readable name of the channel.
    fn name(&self) -> &str;

    /// Send a message through this channel.
    async fn send(&self, message: SendMessage) -> anyhow::Result<()>;

    /// Listen for one inbound message (blocking).
    /// Returns `None` when the channel is closed.
    async fn listen(&self) -> anyhow::Result<Option<ChannelMessage>>;

    /// Check whether the channel backend is healthy.
    async fn health_check(&self) -> anyhow::Result<bool>;
}

// ---------------------------------------------------------------------------
// CLI channel implementation
// ---------------------------------------------------------------------------

/// A channel that reads from stdin and writes to stdout.
#[derive(Debug, Clone, Default)]
pub struct CliChannel;

#[async_trait]
impl Channel for CliChannel {
    fn name(&self) -> &str {
        "cli"
    }

    async fn send(&self, message: SendMessage) -> anyhow::Result<()> {
        println!("{}", message.content);
        Ok(())
    }

    async fn listen(&self) -> anyhow::Result<Option<ChannelMessage>> {
        let mut line = String::new();
        let bytes = tokio::task::spawn_blocking(move || {
            std::io::stdin().read_line(&mut line).map(|b| (b, line))
        })
        .await??;
        if bytes.0 == 0 {
            return Ok(None);
        }
        Ok(Some(ChannelMessage {
            channel: "cli".to_string(),
            sender: "user".to_string(),
            content: bytes.1.trim().to_string(),
            timestamp: Utc::now(),
            metadata: serde_json::json!({}),
        }))
    }

    async fn health_check(&self) -> anyhow::Result<bool> {
        Ok(true)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn cli_channel_name() {
        let ch = CliChannel;
        assert_eq!(ch.name(), "cli");
    }

    #[tokio::test]
    async fn cli_channel_health_check() {
        let ch = CliChannel;
        assert!(ch.health_check().await.unwrap());
    }

    #[test]
    fn channel_message_serialization() {
        let msg = ChannelMessage {
            channel: "test".to_string(),
            sender: "alice".to_string(),
            content: "hello".to_string(),
            timestamp: Utc::now(),
            metadata: serde_json::json!({"key": "value"}),
        };
        let json = serde_json::to_string(&msg).unwrap();
        let round: ChannelMessage = serde_json::from_str(&json).unwrap();
        assert_eq!(round.sender, "alice");
        assert_eq!(round.content, "hello");
    }

    #[test]
    fn send_message_construction() {
        let msg = SendMessage {
            content: "response".to_string(),
            recipient: Some("bob".to_string()),
            metadata: serde_json::json!({}),
        };
        assert_eq!(msg.content, "response");
        assert_eq!(msg.recipient.as_deref(), Some("bob"));
    }
}

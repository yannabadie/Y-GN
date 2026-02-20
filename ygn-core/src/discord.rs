//! Discord channel adapter.
//!
//! Provides a Discord bot integration as a Channel implementation.
//! Uses a `DiscordTransport` trait to abstract the HTTP/WebSocket layer,
//! enabling offline testing with `MockDiscordTransport`.

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;

use crate::channel::{Channel, ChannelMessage, SendMessage};

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/// Configuration for a Discord bot channel.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscordConfig {
    /// Bot token from the Discord Developer Portal.
    pub token: String,
    /// Optional guild (server) filter. When set, only messages from this guild
    /// are processed.
    pub guild_id: Option<String>,
    /// Whitelist of allowed channel IDs. Empty means allow all.
    pub allowed_channel_ids: Vec<String>,
}

// ---------------------------------------------------------------------------
// Message
// ---------------------------------------------------------------------------

/// A message received from the Discord API.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscordMessage {
    /// Unique message snowflake ID.
    pub id: String,
    /// The channel the message was sent in.
    pub channel_id: String,
    /// The author's username.
    pub author: String,
    /// Text content of the message.
    pub content: String,
    /// When the message was created.
    pub timestamp: DateTime<Utc>,
}

// ---------------------------------------------------------------------------
// Transport trait
// ---------------------------------------------------------------------------

/// Abstracts the HTTP/WebSocket layer for Discord API calls.
#[async_trait]
pub trait DiscordTransport: Send + Sync {
    /// Send a text message to the given channel.
    async fn send(&self, channel_id: &str, content: &str) -> anyhow::Result<()>;

    /// Receive pending messages from subscribed channels.
    async fn receive(&self) -> anyhow::Result<Vec<DiscordMessage>>;
}

// ---------------------------------------------------------------------------
// Mock transport (for tests)
// ---------------------------------------------------------------------------

/// A mock transport that stores messages in memory for testing.
pub struct MockDiscordTransport {
    incoming: Mutex<Vec<DiscordMessage>>,
    sent: Mutex<Vec<(String, String)>>,
}

impl Default for MockDiscordTransport {
    fn default() -> Self {
        Self::new()
    }
}

impl MockDiscordTransport {
    /// Create a new empty mock transport.
    pub fn new() -> Self {
        Self {
            incoming: Mutex::new(Vec::new()),
            sent: Mutex::new(Vec::new()),
        }
    }

    /// Queue an incoming message that will be returned by `receive`.
    pub async fn queue_message(&self, msg: DiscordMessage) {
        self.incoming.lock().await.push(msg);
    }

    /// Return a snapshot of all sent messages as `(channel_id, content)`.
    pub async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl DiscordTransport for MockDiscordTransport {
    async fn send(&self, channel_id: &str, content: &str) -> anyhow::Result<()> {
        self.sent
            .lock()
            .await
            .push((channel_id.to_string(), content.to_string()));
        Ok(())
    }

    async fn receive(&self) -> anyhow::Result<Vec<DiscordMessage>> {
        let mut queue = self.incoming.lock().await;
        let messages = queue.drain(..).collect();
        Ok(messages)
    }
}

// ---------------------------------------------------------------------------
// DiscordChannel
// ---------------------------------------------------------------------------

/// A `Channel` implementation backed by the Discord Bot API.
pub struct DiscordChannel {
    config: DiscordConfig,
    transport: Box<dyn DiscordTransport>,
}

impl DiscordChannel {
    /// Create a new Discord channel with the given config and transport.
    pub fn new(config: DiscordConfig, transport: Box<dyn DiscordTransport>) -> Self {
        Self { config, transport }
    }

    /// Check whether a channel ID is allowed by the whitelist.
    fn is_channel_allowed(&self, channel_id: &str) -> bool {
        if self.config.allowed_channel_ids.is_empty() {
            return true;
        }
        self.config
            .allowed_channel_ids
            .iter()
            .any(|id| id == channel_id)
    }
}

#[async_trait]
impl Channel for DiscordChannel {
    fn name(&self) -> &str {
        "discord"
    }

    async fn send(&self, message: SendMessage) -> anyhow::Result<()> {
        let channel_id = message
            .metadata
            .get("channel_id")
            .and_then(|v| v.as_str())
            .unwrap_or("0");
        self.transport.send(channel_id, &message.content).await
    }

    async fn listen(&self) -> anyhow::Result<Option<ChannelMessage>> {
        let messages = self.transport.receive().await?;

        for msg in messages {
            if !self.is_channel_allowed(&msg.channel_id) {
                continue;
            }
            return Ok(Some(ChannelMessage {
                channel: "discord".to_string(),
                sender: msg.author,
                content: msg.content,
                timestamp: msg.timestamp,
                metadata: serde_json::json!({
                    "message_id": msg.id,
                    "channel_id": msg.channel_id,
                }),
            }));
        }

        Ok(None)
    }

    async fn health_check(&self) -> anyhow::Result<bool> {
        // In mock/test scenarios this always succeeds.
        // A real implementation would call the /users/@me endpoint.
        Ok(true)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;

    fn make_config(allowed: Vec<String>) -> DiscordConfig {
        DiscordConfig {
            token: "test-bot-token".to_string(),
            guild_id: Some("guild-123".to_string()),
            allowed_channel_ids: allowed,
        }
    }

    fn make_message(id: &str, channel_id: &str, author: &str, content: &str) -> DiscordMessage {
        DiscordMessage {
            id: id.to_string(),
            channel_id: channel_id.to_string(),
            author: author.to_string(),
            content: content.to_string(),
            timestamp: Utc::now(),
        }
    }

    // -----------------------------------------------------------------------
    // Helper: wraps Arc<MockDiscordTransport> to satisfy Box<dyn ...>
    // -----------------------------------------------------------------------

    struct ArcTransport(Arc<MockDiscordTransport>);

    #[async_trait]
    impl DiscordTransport for ArcTransport {
        async fn send(&self, channel_id: &str, content: &str) -> anyhow::Result<()> {
            self.0.send(channel_id, content).await
        }

        async fn receive(&self) -> anyhow::Result<Vec<DiscordMessage>> {
            self.0.receive().await
        }
    }

    // -----------------------------------------------------------------------
    // Tests
    // -----------------------------------------------------------------------

    #[test]
    fn discord_config_serialization() {
        let config = make_config(vec!["ch-1".to_string(), "ch-2".to_string()]);
        let json = serde_json::to_string(&config).unwrap();
        let round: DiscordConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(round.token, "test-bot-token");
        assert_eq!(round.guild_id, Some("guild-123".to_string()));
        assert_eq!(round.allowed_channel_ids, vec!["ch-1", "ch-2"]);
    }

    #[test]
    fn discord_config_serialization_no_guild() {
        let config = DiscordConfig {
            token: "tok".to_string(),
            guild_id: None,
            allowed_channel_ids: vec![],
        };
        let json = serde_json::to_string(&config).unwrap();
        let round: DiscordConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(round.guild_id, None);
        assert!(round.allowed_channel_ids.is_empty());
    }

    #[tokio::test]
    async fn discord_channel_name() {
        let transport = MockDiscordTransport::new();
        let channel = DiscordChannel::new(make_config(vec![]), Box::new(transport));
        assert_eq!(channel.name(), "discord");
    }

    #[tokio::test]
    async fn health_check_returns_true() {
        let transport = MockDiscordTransport::new();
        let channel = DiscordChannel::new(make_config(vec![]), Box::new(transport));
        assert!(channel.health_check().await.unwrap());
    }

    #[tokio::test]
    async fn send_delegates_to_transport() {
        let shared = Arc::new(MockDiscordTransport::new());
        let channel = DiscordChannel {
            config: make_config(vec![]),
            transport: Box::new(ArcTransport(Arc::clone(&shared))),
        };

        let msg = SendMessage {
            content: "Hello Discord!".to_string(),
            recipient: None,
            metadata: serde_json::json!({"channel_id": "chan-42"}),
        };
        channel.send(msg).await.unwrap();

        let sent = shared.sent_messages().await;
        assert_eq!(sent.len(), 1);
        assert_eq!(sent[0].0, "chan-42");
        assert_eq!(sent[0].1, "Hello Discord!");
    }

    #[tokio::test]
    async fn send_uses_default_channel_id_when_missing() {
        let shared = Arc::new(MockDiscordTransport::new());
        let channel = DiscordChannel {
            config: make_config(vec![]),
            transport: Box::new(ArcTransport(Arc::clone(&shared))),
        };

        let msg = SendMessage {
            content: "fallback".to_string(),
            recipient: None,
            metadata: serde_json::json!({}),
        };
        channel.send(msg).await.unwrap();

        let sent = shared.sent_messages().await;
        assert_eq!(sent[0].0, "0");
    }

    #[tokio::test]
    async fn listen_returns_messages() {
        let transport = Arc::new(MockDiscordTransport::new());
        transport
            .queue_message(make_message("1", "chan-100", "alice", "hi"))
            .await;

        let channel = DiscordChannel {
            config: make_config(vec![]),
            transport: Box::new(ArcTransport(Arc::clone(&transport))),
        };

        let result = channel.listen().await.unwrap();
        assert!(result.is_some());
        let cm = result.unwrap();
        assert_eq!(cm.content, "hi");
        assert_eq!(cm.channel, "discord");
        assert_eq!(cm.sender, "alice");
    }

    #[tokio::test]
    async fn listen_filters_by_allowed_channel_ids() {
        let transport = Arc::new(MockDiscordTransport::new());
        transport
            .queue_message(make_message("1", "chan-ok", "alice", "allowed"))
            .await;
        transport
            .queue_message(make_message("2", "chan-blocked", "bob", "blocked"))
            .await;

        let channel = DiscordChannel {
            config: make_config(vec!["chan-ok".to_string()]),
            transport: Box::new(ArcTransport(Arc::clone(&transport))),
        };

        let result = channel.listen().await.unwrap();
        assert!(result.is_some());
        assert_eq!(result.unwrap().content, "allowed");
    }

    #[tokio::test]
    async fn listen_allows_all_when_empty_whitelist() {
        let transport = Arc::new(MockDiscordTransport::new());
        transport
            .queue_message(make_message("1", "any-channel", "eve", "anyone"))
            .await;

        let channel = DiscordChannel {
            config: make_config(vec![]),
            transport: Box::new(ArcTransport(Arc::clone(&transport))),
        };

        let result = channel.listen().await.unwrap();
        assert!(result.is_some());
        assert_eq!(result.unwrap().content, "anyone");
    }

    #[tokio::test]
    async fn listen_returns_none_when_all_filtered() {
        let transport = Arc::new(MockDiscordTransport::new());
        transport
            .queue_message(make_message("1", "chan-blocked", "bob", "nope"))
            .await;

        let channel = DiscordChannel {
            config: make_config(vec!["chan-ok".to_string()]),
            transport: Box::new(ArcTransport(Arc::clone(&transport))),
        };

        let result = channel.listen().await.unwrap();
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn mock_transport_stores_sent_messages() {
        let transport = MockDiscordTransport::new();
        transport.send("ch1", "msg1").await.unwrap();
        transport.send("ch2", "msg2").await.unwrap();

        let sent = transport.sent_messages().await;
        assert_eq!(sent.len(), 2);
        assert_eq!(sent[0], ("ch1".to_string(), "msg1".to_string()));
        assert_eq!(sent[1], ("ch2".to_string(), "msg2".to_string()));
    }

    #[test]
    fn discord_message_construction() {
        let msg = make_message("snowflake-1", "chan-42", "testuser", "hello");
        assert_eq!(msg.id, "snowflake-1");
        assert_eq!(msg.channel_id, "chan-42");
        assert_eq!(msg.author, "testuser");
        assert_eq!(msg.content, "hello");
    }

    #[test]
    fn discord_message_serialization() {
        let msg = make_message("id-1", "chan-1", "alice", "test content");
        let json = serde_json::to_string(&msg).unwrap();
        let round: DiscordMessage = serde_json::from_str(&json).unwrap();
        assert_eq!(round.id, "id-1");
        assert_eq!(round.content, "test content");
    }
}

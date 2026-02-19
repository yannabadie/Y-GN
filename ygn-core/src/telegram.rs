//! Telegram channel adapter.
//!
//! Provides a Telegram bot integration as a Channel implementation.
//! Uses a `TelegramTransport` trait to abstract the HTTP layer, enabling
//! offline testing with `MockTelegramTransport`.

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;

use crate::channel::{Channel, ChannelMessage, SendMessage};

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/// Configuration for a Telegram bot channel.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TelegramConfig {
    /// Bot API token from @BotFather.
    pub bot_token: String,
    /// Whitelist of allowed chat IDs. Empty means allow all.
    pub allowed_chat_ids: Vec<i64>,
    /// Long-polling timeout in seconds.
    #[serde(default = "default_polling_timeout")]
    pub polling_timeout_secs: u64,
}

fn default_polling_timeout() -> u64 {
    30
}

// ---------------------------------------------------------------------------
// Message
// ---------------------------------------------------------------------------

/// A message received from the Telegram API.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TelegramMessage {
    pub update_id: i64,
    pub chat_id: i64,
    pub from_username: Option<String>,
    pub text: String,
    pub timestamp: DateTime<Utc>,
}

// ---------------------------------------------------------------------------
// Transport trait
// ---------------------------------------------------------------------------

/// Abstracts the HTTP layer for Telegram Bot API calls.
#[async_trait]
pub trait TelegramTransport: Send + Sync {
    /// Fetch new updates starting from `offset`.
    async fn get_updates(&self, offset: i64, timeout: u64) -> anyhow::Result<Vec<TelegramMessage>>;

    /// Send a text message to the given chat.
    async fn send_message(&self, chat_id: i64, text: &str) -> anyhow::Result<()>;
}

// ---------------------------------------------------------------------------
// Mock transport (for tests)
// ---------------------------------------------------------------------------

/// A mock transport that stores messages in memory for testing.
pub struct MockTelegramTransport {
    incoming: Mutex<Vec<TelegramMessage>>,
    sent: Mutex<Vec<(i64, String)>>,
}

impl Default for MockTelegramTransport {
    fn default() -> Self {
        Self::new()
    }
}

impl MockTelegramTransport {
    /// Create a new empty mock transport.
    pub fn new() -> Self {
        Self {
            incoming: Mutex::new(Vec::new()),
            sent: Mutex::new(Vec::new()),
        }
    }

    /// Queue an incoming message that will be returned by `get_updates`.
    pub async fn queue_message(&self, msg: TelegramMessage) {
        self.incoming.lock().await.push(msg);
    }

    /// Return a snapshot of all sent messages.
    pub async fn sent_messages(&self) -> Vec<(i64, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl TelegramTransport for MockTelegramTransport {
    async fn get_updates(
        &self,
        _offset: i64,
        _timeout: u64,
    ) -> anyhow::Result<Vec<TelegramMessage>> {
        let mut queue = self.incoming.lock().await;
        let messages = queue.drain(..).collect();
        Ok(messages)
    }

    async fn send_message(&self, chat_id: i64, text: &str) -> anyhow::Result<()> {
        self.sent.lock().await.push((chat_id, text.to_string()));
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// TelegramChannel
// ---------------------------------------------------------------------------

/// A `Channel` implementation backed by the Telegram Bot API.
pub struct TelegramChannel {
    config: TelegramConfig,
    transport: Box<dyn TelegramTransport>,
}

impl TelegramChannel {
    /// Create a new Telegram channel with the given config and transport.
    pub fn new(config: TelegramConfig, transport: Box<dyn TelegramTransport>) -> Self {
        Self { config, transport }
    }

    /// Check whether a chat ID is allowed by the whitelist.
    fn is_chat_allowed(&self, chat_id: i64) -> bool {
        if self.config.allowed_chat_ids.is_empty() {
            return true;
        }
        self.config.allowed_chat_ids.contains(&chat_id)
    }
}

#[async_trait]
impl Channel for TelegramChannel {
    fn name(&self) -> &str {
        "telegram"
    }

    async fn send(&self, message: SendMessage) -> anyhow::Result<()> {
        // Extract chat_id from metadata, or use 0 as default.
        let chat_id = message
            .metadata
            .get("chat_id")
            .and_then(|v| v.as_i64())
            .unwrap_or(0);
        self.transport.send_message(chat_id, &message.content).await
    }

    async fn listen(&self) -> anyhow::Result<Option<ChannelMessage>> {
        let messages = self
            .transport
            .get_updates(0, self.config.polling_timeout_secs)
            .await?;

        for msg in messages {
            if !self.is_chat_allowed(msg.chat_id) {
                continue;
            }
            return Ok(Some(ChannelMessage {
                channel: "telegram".to_string(),
                sender: msg.from_username.unwrap_or_else(|| msg.chat_id.to_string()),
                content: msg.text,
                timestamp: msg.timestamp,
                metadata: serde_json::json!({
                    "chat_id": msg.chat_id,
                    "update_id": msg.update_id,
                }),
            }));
        }

        Ok(None)
    }

    async fn health_check(&self) -> anyhow::Result<bool> {
        // In mock/test scenarios this always succeeds.
        // A real implementation would call the getMe endpoint.
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

    fn make_config(allowed: Vec<i64>) -> TelegramConfig {
        TelegramConfig {
            bot_token: "test-token".to_string(),
            allowed_chat_ids: allowed,
            polling_timeout_secs: 30,
        }
    }

    fn make_message(update_id: i64, chat_id: i64, text: &str) -> TelegramMessage {
        TelegramMessage {
            update_id,
            chat_id,
            from_username: Some("testuser".to_string()),
            text: text.to_string(),
            timestamp: Utc::now(),
        }
    }

    #[tokio::test]
    async fn telegram_channel_name() {
        let transport = MockTelegramTransport::new();
        let channel = TelegramChannel::new(make_config(vec![]), Box::new(transport));
        assert_eq!(channel.name(), "telegram");
    }

    #[tokio::test]
    async fn send_delegates_to_transport() {
        let shared = Arc::new(MockTelegramTransport::new());
        let channel = TelegramChannel {
            config: make_config(vec![]),
            transport: Box::new(ArcTransport(Arc::clone(&shared))),
        };

        let msg = SendMessage {
            content: "Hello Telegram!".to_string(),
            recipient: None,
            metadata: serde_json::json!({"chat_id": 42}),
        };
        channel.send(msg).await.unwrap();

        let sent = shared.sent_messages().await;
        assert_eq!(sent.len(), 1);
        assert_eq!(sent[0].0, 42);
        assert_eq!(sent[0].1, "Hello Telegram!");
    }

    #[tokio::test]
    async fn listen_returns_messages() {
        let transport = Arc::new(MockTelegramTransport::new());
        transport.queue_message(make_message(1, 100, "hi")).await;

        let channel = TelegramChannel {
            config: make_config(vec![]),
            transport: Box::new(ArcTransport(Arc::clone(&transport))),
        };

        let result = channel.listen().await.unwrap();
        assert!(result.is_some());
        let cm = result.unwrap();
        assert_eq!(cm.content, "hi");
        assert_eq!(cm.channel, "telegram");
        assert_eq!(cm.sender, "testuser");
    }

    #[tokio::test]
    async fn listen_filters_by_allowed_chat_ids() {
        let transport = Arc::new(MockTelegramTransport::new());
        transport
            .queue_message(make_message(1, 100, "allowed"))
            .await;
        transport
            .queue_message(make_message(2, 999, "blocked"))
            .await;

        let channel = TelegramChannel {
            config: make_config(vec![100]),
            transport: Box::new(ArcTransport(Arc::clone(&transport))),
        };

        let result = channel.listen().await.unwrap();
        assert!(result.is_some());
        assert_eq!(result.unwrap().content, "allowed");
    }

    #[tokio::test]
    async fn listen_allows_all_when_empty_whitelist() {
        let transport = Arc::new(MockTelegramTransport::new());
        transport
            .queue_message(make_message(1, 777, "anyone"))
            .await;

        let channel = TelegramChannel {
            config: make_config(vec![]),
            transport: Box::new(ArcTransport(Arc::clone(&transport))),
        };

        let result = channel.listen().await.unwrap();
        assert!(result.is_some());
        assert_eq!(result.unwrap().content, "anyone");
    }

    #[tokio::test]
    async fn health_check_returns_true() {
        let transport = MockTelegramTransport::new();
        let channel = TelegramChannel::new(make_config(vec![]), Box::new(transport));
        assert!(channel.health_check().await.unwrap());
    }

    #[test]
    fn telegram_config_serialization() {
        let config = make_config(vec![1, 2, 3]);
        let json = serde_json::to_string(&config).unwrap();
        let round: TelegramConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(round.bot_token, "test-token");
        assert_eq!(round.allowed_chat_ids, vec![1, 2, 3]);
        assert_eq!(round.polling_timeout_secs, 30);
    }

    #[test]
    fn telegram_message_construction() {
        let msg = make_message(42, 100, "hello");
        assert_eq!(msg.update_id, 42);
        assert_eq!(msg.chat_id, 100);
        assert_eq!(msg.from_username.as_deref(), Some("testuser"));
        assert_eq!(msg.text, "hello");
    }

    // -----------------------------------------------------------------------
    // Helper: wraps Arc<MockTelegramTransport> to satisfy Box<dyn …>
    // -----------------------------------------------------------------------

    struct ArcTransport(Arc<MockTelegramTransport>);

    #[async_trait]
    impl TelegramTransport for ArcTransport {
        async fn get_updates(
            &self,
            offset: i64,
            timeout: u64,
        ) -> anyhow::Result<Vec<TelegramMessage>> {
            self.0.get_updates(offset, timeout).await
        }

        async fn send_message(&self, chat_id: i64, text: &str) -> anyhow::Result<()> {
            self.0.send_message(chat_id, text).await
        }
    }
}

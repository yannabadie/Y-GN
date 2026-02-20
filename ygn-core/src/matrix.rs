//! Matrix channel adapter.
//!
//! Provides a Matrix client integration as a Channel implementation.
//! Uses a `MatrixTransport` trait to abstract the HTTP layer, enabling
//! offline testing with `MockMatrixTransport`.

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;

use crate::channel::{Channel, ChannelMessage, SendMessage};

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/// Configuration for a Matrix channel.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MatrixConfig {
    /// Homeserver URL, e.g. "https://matrix.org".
    pub homeserver_url: String,
    /// Access token for authenticating with the homeserver.
    pub access_token: String,
    /// Room IDs to join and listen in. Empty means allow all.
    pub room_ids: Vec<String>,
}

// ---------------------------------------------------------------------------
// Message
// ---------------------------------------------------------------------------

/// A message received from a Matrix room.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MatrixMessage {
    /// The event ID (e.g. "$abc123:matrix.org").
    pub event_id: String,
    /// The room the message was sent in.
    pub room_id: String,
    /// The sender's Matrix ID (e.g. "@user:matrix.org").
    pub sender: String,
    /// Text body of the message.
    pub body: String,
    /// Server-side timestamp.
    pub timestamp: DateTime<Utc>,
}

// ---------------------------------------------------------------------------
// Transport trait
// ---------------------------------------------------------------------------

/// Abstracts the HTTP layer for Matrix Client-Server API calls.
#[async_trait]
pub trait MatrixTransport: Send + Sync {
    /// Send a text message to the given room.
    async fn send(&self, room_id: &str, body: &str) -> anyhow::Result<()>;

    /// Receive pending messages via long-poll / sync.
    async fn receive(&self) -> anyhow::Result<Vec<MatrixMessage>>;
}

// ---------------------------------------------------------------------------
// Mock transport (for tests)
// ---------------------------------------------------------------------------

/// A mock transport that stores messages in memory for testing.
pub struct MockMatrixTransport {
    incoming: Mutex<Vec<MatrixMessage>>,
    sent: Mutex<Vec<(String, String)>>,
}

impl Default for MockMatrixTransport {
    fn default() -> Self {
        Self::new()
    }
}

impl MockMatrixTransport {
    /// Create a new empty mock transport.
    pub fn new() -> Self {
        Self {
            incoming: Mutex::new(Vec::new()),
            sent: Mutex::new(Vec::new()),
        }
    }

    /// Queue an incoming message that will be returned by `receive`.
    pub async fn queue_message(&self, msg: MatrixMessage) {
        self.incoming.lock().await.push(msg);
    }

    /// Return a snapshot of all sent messages as `(room_id, body)`.
    pub async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl MatrixTransport for MockMatrixTransport {
    async fn send(&self, room_id: &str, body: &str) -> anyhow::Result<()> {
        self.sent
            .lock()
            .await
            .push((room_id.to_string(), body.to_string()));
        Ok(())
    }

    async fn receive(&self) -> anyhow::Result<Vec<MatrixMessage>> {
        let mut queue = self.incoming.lock().await;
        let messages = queue.drain(..).collect();
        Ok(messages)
    }
}

// ---------------------------------------------------------------------------
// MatrixChannel
// ---------------------------------------------------------------------------

/// A `Channel` implementation backed by the Matrix Client-Server API.
pub struct MatrixChannel {
    config: MatrixConfig,
    transport: Box<dyn MatrixTransport>,
}

impl MatrixChannel {
    /// Create a new Matrix channel with the given config and transport.
    pub fn new(config: MatrixConfig, transport: Box<dyn MatrixTransport>) -> Self {
        Self { config, transport }
    }

    /// Check whether a room ID is allowed by the configured room list.
    fn is_room_allowed(&self, room_id: &str) -> bool {
        if self.config.room_ids.is_empty() {
            return true;
        }
        self.config.room_ids.iter().any(|id| id == room_id)
    }
}

#[async_trait]
impl Channel for MatrixChannel {
    fn name(&self) -> &str {
        "matrix"
    }

    async fn send(&self, message: SendMessage) -> anyhow::Result<()> {
        let room_id = message
            .metadata
            .get("room_id")
            .and_then(|v| v.as_str())
            .unwrap_or("!unknown:localhost");
        self.transport.send(room_id, &message.content).await
    }

    async fn listen(&self) -> anyhow::Result<Option<ChannelMessage>> {
        let messages = self.transport.receive().await?;

        for msg in messages {
            if !self.is_room_allowed(&msg.room_id) {
                continue;
            }
            return Ok(Some(ChannelMessage {
                channel: "matrix".to_string(),
                sender: msg.sender,
                content: msg.body,
                timestamp: msg.timestamp,
                metadata: serde_json::json!({
                    "event_id": msg.event_id,
                    "room_id": msg.room_id,
                }),
            }));
        }

        Ok(None)
    }

    async fn health_check(&self) -> anyhow::Result<bool> {
        // In mock/test scenarios this always succeeds.
        // A real implementation would call /_matrix/client/versions.
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

    fn make_config(room_ids: Vec<String>) -> MatrixConfig {
        MatrixConfig {
            homeserver_url: "https://matrix.example.org".to_string(),
            access_token: "test-access-token".to_string(),
            room_ids,
        }
    }

    fn make_message(event_id: &str, room_id: &str, sender: &str, body: &str) -> MatrixMessage {
        MatrixMessage {
            event_id: event_id.to_string(),
            room_id: room_id.to_string(),
            sender: sender.to_string(),
            body: body.to_string(),
            timestamp: Utc::now(),
        }
    }

    // -----------------------------------------------------------------------
    // Helper: wraps Arc<MockMatrixTransport> to satisfy Box<dyn ...>
    // -----------------------------------------------------------------------

    struct ArcTransport(Arc<MockMatrixTransport>);

    #[async_trait]
    impl MatrixTransport for ArcTransport {
        async fn send(&self, room_id: &str, body: &str) -> anyhow::Result<()> {
            self.0.send(room_id, body).await
        }

        async fn receive(&self) -> anyhow::Result<Vec<MatrixMessage>> {
            self.0.receive().await
        }
    }

    // -----------------------------------------------------------------------
    // Tests
    // -----------------------------------------------------------------------

    #[test]
    fn matrix_config_serialization() {
        let config = make_config(vec!["!room1:matrix.org".to_string()]);
        let json = serde_json::to_string(&config).unwrap();
        let round: MatrixConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(round.homeserver_url, "https://matrix.example.org");
        assert_eq!(round.access_token, "test-access-token");
        assert_eq!(round.room_ids, vec!["!room1:matrix.org"]);
    }

    #[test]
    fn matrix_config_empty_rooms() {
        let config = make_config(vec![]);
        let json = serde_json::to_string(&config).unwrap();
        let round: MatrixConfig = serde_json::from_str(&json).unwrap();
        assert!(round.room_ids.is_empty());
    }

    #[tokio::test]
    async fn matrix_channel_name() {
        let transport = MockMatrixTransport::new();
        let channel = MatrixChannel::new(make_config(vec![]), Box::new(transport));
        assert_eq!(channel.name(), "matrix");
    }

    #[tokio::test]
    async fn health_check_returns_true() {
        let transport = MockMatrixTransport::new();
        let channel = MatrixChannel::new(make_config(vec![]), Box::new(transport));
        assert!(channel.health_check().await.unwrap());
    }

    #[tokio::test]
    async fn send_delegates_to_transport() {
        let shared = Arc::new(MockMatrixTransport::new());
        let channel = MatrixChannel {
            config: make_config(vec![]),
            transport: Box::new(ArcTransport(Arc::clone(&shared))),
        };

        let msg = SendMessage {
            content: "Hello Matrix!".to_string(),
            recipient: None,
            metadata: serde_json::json!({"room_id": "!room-42:matrix.org"}),
        };
        channel.send(msg).await.unwrap();

        let sent = shared.sent_messages().await;
        assert_eq!(sent.len(), 1);
        assert_eq!(sent[0].0, "!room-42:matrix.org");
        assert_eq!(sent[0].1, "Hello Matrix!");
    }

    #[tokio::test]
    async fn send_uses_default_room_when_missing() {
        let shared = Arc::new(MockMatrixTransport::new());
        let channel = MatrixChannel {
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
        assert_eq!(sent[0].0, "!unknown:localhost");
    }

    #[tokio::test]
    async fn listen_returns_messages() {
        let transport = Arc::new(MockMatrixTransport::new());
        transport
            .queue_message(make_message(
                "$evt1:matrix.org",
                "!room-100:matrix.org",
                "@alice:matrix.org",
                "hi",
            ))
            .await;

        let channel = MatrixChannel {
            config: make_config(vec![]),
            transport: Box::new(ArcTransport(Arc::clone(&transport))),
        };

        let result = channel.listen().await.unwrap();
        assert!(result.is_some());
        let cm = result.unwrap();
        assert_eq!(cm.content, "hi");
        assert_eq!(cm.channel, "matrix");
        assert_eq!(cm.sender, "@alice:matrix.org");
    }

    #[tokio::test]
    async fn listen_filters_by_room_ids() {
        let transport = Arc::new(MockMatrixTransport::new());
        transport
            .queue_message(make_message(
                "$evt1",
                "!allowed:matrix.org",
                "@alice:matrix.org",
                "allowed",
            ))
            .await;
        transport
            .queue_message(make_message(
                "$evt2",
                "!blocked:matrix.org",
                "@bob:matrix.org",
                "blocked",
            ))
            .await;

        let channel = MatrixChannel {
            config: make_config(vec!["!allowed:matrix.org".to_string()]),
            transport: Box::new(ArcTransport(Arc::clone(&transport))),
        };

        let result = channel.listen().await.unwrap();
        assert!(result.is_some());
        assert_eq!(result.unwrap().content, "allowed");
    }

    #[tokio::test]
    async fn listen_allows_all_when_empty_room_list() {
        let transport = Arc::new(MockMatrixTransport::new());
        transport
            .queue_message(make_message(
                "$evt1",
                "!any-room:matrix.org",
                "@eve:matrix.org",
                "anyone",
            ))
            .await;

        let channel = MatrixChannel {
            config: make_config(vec![]),
            transport: Box::new(ArcTransport(Arc::clone(&transport))),
        };

        let result = channel.listen().await.unwrap();
        assert!(result.is_some());
        assert_eq!(result.unwrap().content, "anyone");
    }

    #[tokio::test]
    async fn listen_returns_none_when_all_filtered() {
        let transport = Arc::new(MockMatrixTransport::new());
        transport
            .queue_message(make_message(
                "$evt1",
                "!blocked:matrix.org",
                "@bob:matrix.org",
                "nope",
            ))
            .await;

        let channel = MatrixChannel {
            config: make_config(vec!["!allowed:matrix.org".to_string()]),
            transport: Box::new(ArcTransport(Arc::clone(&transport))),
        };

        let result = channel.listen().await.unwrap();
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn mock_transport_stores_sent_messages() {
        let transport = MockMatrixTransport::new();
        transport.send("!room1:matrix.org", "msg1").await.unwrap();
        transport.send("!room2:matrix.org", "msg2").await.unwrap();

        let sent = transport.sent_messages().await;
        assert_eq!(sent.len(), 2);
        assert_eq!(
            sent[0],
            ("!room1:matrix.org".to_string(), "msg1".to_string())
        );
        assert_eq!(
            sent[1],
            ("!room2:matrix.org".to_string(), "msg2".to_string())
        );
    }

    #[test]
    fn matrix_message_construction() {
        let msg = make_message("$evt1:mx.org", "!room:mx.org", "@user:mx.org", "hello");
        assert_eq!(msg.event_id, "$evt1:mx.org");
        assert_eq!(msg.room_id, "!room:mx.org");
        assert_eq!(msg.sender, "@user:mx.org");
        assert_eq!(msg.body, "hello");
    }

    #[test]
    fn matrix_message_serialization() {
        let msg = make_message("$evt1", "!room1:mx.org", "@alice:mx.org", "test content");
        let json = serde_json::to_string(&msg).unwrap();
        let round: MatrixMessage = serde_json::from_str(&json).unwrap();
        assert_eq!(round.event_id, "$evt1");
        assert_eq!(round.body, "test content");
    }
}

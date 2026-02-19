//! LLM Provider trait and types.
//!
//! Defines the interface for LLM backends (Anthropic, OpenAI, Ollama, etc.)
//! based on ZeroClaw's Provider trait architecture.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};

use crate::tool::ToolSpec;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Describes what a provider supports.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderCapabilities {
    pub native_tool_calling: bool,
    pub vision: bool,
    pub streaming: bool,
}

/// Role in a conversation turn.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ChatRole {
    System,
    User,
    Assistant,
    Tool,
}

/// A single message within a chat request.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: ChatRole,
    pub content: String,
}

/// Request sent to a provider.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatRequest {
    pub model: String,
    pub messages: Vec<ChatMessage>,
    pub max_tokens: Option<u32>,
    pub temperature: Option<f64>,
}

/// A tool call returned by the provider.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCall {
    pub tool_name: String,
    pub arguments: serde_json::Value,
}

/// Response returned by a provider.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatResponse {
    pub content: String,
    pub tool_calls: Vec<ToolCall>,
    pub usage: Option<TokenUsage>,
}

/// Token usage information.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenUsage {
    pub prompt_tokens: u32,
    pub completion_tokens: u32,
}

// ---------------------------------------------------------------------------
// Trait
// ---------------------------------------------------------------------------

/// Core trait every LLM provider must implement.
#[async_trait]
pub trait Provider: Send + Sync {
    /// Human-readable name of the provider.
    fn name(&self) -> &str;

    /// Capabilities exposed by this provider.
    fn capabilities(&self) -> ProviderCapabilities;

    /// Send a chat request and receive a response.
    async fn chat(&self, request: ChatRequest) -> anyhow::Result<ChatResponse>;

    /// Send a chat request with tool definitions.
    async fn chat_with_tools(
        &self,
        request: ChatRequest,
        tools: &[ToolSpec],
    ) -> anyhow::Result<ChatResponse>;
}

// ---------------------------------------------------------------------------
// Stub implementation (for testing / M1)
// ---------------------------------------------------------------------------

/// A provider that returns canned responses. Useful for tests and offline
/// development.
#[derive(Debug, Clone)]
pub struct StubProvider {
    pub response_text: String,
}

impl Default for StubProvider {
    fn default() -> Self {
        Self {
            response_text: "Hello from StubProvider".to_string(),
        }
    }
}

#[async_trait]
impl Provider for StubProvider {
    fn name(&self) -> &str {
        "stub"
    }

    fn capabilities(&self) -> ProviderCapabilities {
        ProviderCapabilities {
            native_tool_calling: false,
            vision: false,
            streaming: false,
        }
    }

    async fn chat(&self, _request: ChatRequest) -> anyhow::Result<ChatResponse> {
        Ok(ChatResponse {
            content: self.response_text.clone(),
            tool_calls: vec![],
            usage: Some(TokenUsage {
                prompt_tokens: 0,
                completion_tokens: 0,
            }),
        })
    }

    async fn chat_with_tools(
        &self,
        request: ChatRequest,
        _tools: &[ToolSpec],
    ) -> anyhow::Result<ChatResponse> {
        // Stub ignores tools and delegates to plain chat.
        self.chat(request).await
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_request() -> ChatRequest {
        ChatRequest {
            model: "stub".to_string(),
            messages: vec![ChatMessage {
                role: ChatRole::User,
                content: "Hi".to_string(),
            }],
            max_tokens: Some(100),
            temperature: None,
        }
    }

    #[tokio::test]
    async fn stub_provider_returns_canned_response() {
        let provider = StubProvider::default();
        let resp = provider.chat(sample_request()).await.unwrap();
        assert_eq!(resp.content, "Hello from StubProvider");
        assert!(resp.tool_calls.is_empty());
    }

    #[tokio::test]
    async fn stub_provider_capabilities() {
        let provider = StubProvider::default();
        let caps = provider.capabilities();
        assert!(!caps.native_tool_calling);
        assert!(!caps.vision);
        assert!(!caps.streaming);
    }

    #[tokio::test]
    async fn stub_provider_chat_with_tools_delegates() {
        let provider = StubProvider {
            response_text: "tool-aware".to_string(),
        };
        let resp = provider
            .chat_with_tools(sample_request(), &[])
            .await
            .unwrap();
        assert_eq!(resp.content, "tool-aware");
    }

    #[test]
    fn chat_message_serialization() {
        let msg = ChatMessage {
            role: ChatRole::User,
            content: "hello".to_string(),
        };
        let json = serde_json::to_string(&msg).unwrap();
        let round: ChatMessage = serde_json::from_str(&json).unwrap();
        assert_eq!(round.role, ChatRole::User);
        assert_eq!(round.content, "hello");
    }
}

//! Multi-provider LLM support -- Claude, OpenAI, Gemini, Ollama.
//!
//! Each provider implements the `Provider` trait from `provider.rs` and
//! communicates with its respective API via `reqwest`.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};

use crate::provider::{
    ChatRequest, ChatResponse, ChatRole, Provider, ProviderCapabilities, TokenUsage, ToolCall,
};
use crate::tool::ToolSpec;

// ---------------------------------------------------------------------------
// Provider Configs
// ---------------------------------------------------------------------------

/// Configuration for the Anthropic Claude provider.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaudeConfig {
    pub api_key: String,
    pub model: String,
    pub base_url: Option<String>,
}

/// Configuration for the OpenAI provider.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenAIConfig {
    pub api_key: String,
    pub model: String,
    pub base_url: Option<String>,
}

/// Configuration for the Google Gemini provider.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeminiConfig {
    pub api_key: String,
    pub model: String,
}

/// Configuration for the Ollama (local) provider.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OllamaConfig {
    pub model: String,
    pub base_url: Option<String>,
}

// ---------------------------------------------------------------------------
// Claude Provider
// ---------------------------------------------------------------------------

/// Anthropic Claude provider using the Messages API.
pub struct ClaudeProvider {
    pub config: ClaudeConfig,
    client: reqwest::Client,
}

impl std::fmt::Debug for ClaudeProvider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ClaudeProvider")
            .field("model", &self.config.model)
            .finish()
    }
}

impl ClaudeProvider {
    /// Create a new Claude provider with the given config.
    pub fn new(config: ClaudeConfig) -> Self {
        Self {
            config,
            client: reqwest::Client::new(),
        }
    }

    /// Create a Claude provider from the `ANTHROPIC_API_KEY` env var.
    pub fn from_env() -> Option<Self> {
        let api_key = std::env::var("ANTHROPIC_API_KEY").ok()?;
        Some(Self::new(ClaudeConfig {
            api_key,
            model: "claude-sonnet-4-20250514".to_string(),
            base_url: None,
        }))
    }

    fn base_url(&self) -> &str {
        self.config
            .base_url
            .as_deref()
            .unwrap_or("https://api.anthropic.com")
    }

    /// Build the Anthropic Messages API request body from a ChatRequest.
    fn build_request_body(
        &self,
        request: &ChatRequest,
        tools: Option<&[ToolSpec]>,
    ) -> serde_json::Value {
        // Extract system message if present.
        let system_msg: Option<String> = request
            .messages
            .iter()
            .find(|m| m.role == ChatRole::System)
            .map(|m| m.content.clone());

        // Map non-system messages.
        let messages: Vec<serde_json::Value> = request
            .messages
            .iter()
            .filter(|m| m.role != ChatRole::System)
            .map(|m| {
                serde_json::json!({
                    "role": claude_role(&m.role),
                    "content": m.content,
                })
            })
            .collect();

        let mut body = serde_json::json!({
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens.unwrap_or(4096),
        });

        if let Some(sys) = system_msg {
            body["system"] = serde_json::Value::String(sys);
        }
        if let Some(temp) = request.temperature {
            body["temperature"] = serde_json::json!(temp);
        }
        if let Some(tool_specs) = tools {
            if !tool_specs.is_empty() {
                let tool_defs: Vec<serde_json::Value> = tool_specs
                    .iter()
                    .map(|t| {
                        serde_json::json!({
                            "name": t.name,
                            "description": t.description,
                            "input_schema": t.parameters_schema,
                        })
                    })
                    .collect();
                body["tools"] = serde_json::Value::Array(tool_defs);
            }
        }

        body
    }

    /// Parse an Anthropic Messages API response into a ChatResponse.
    fn parse_response(body: &serde_json::Value) -> anyhow::Result<ChatResponse> {
        let mut content = String::new();
        let mut tool_calls = Vec::new();

        if let Some(blocks) = body.get("content").and_then(|c| c.as_array()) {
            for block in blocks {
                match block.get("type").and_then(|t| t.as_str()) {
                    Some("text") => {
                        if let Some(text) = block.get("text").and_then(|t| t.as_str()) {
                            content.push_str(text);
                        }
                    }
                    Some("tool_use") => {
                        let name = block
                            .get("name")
                            .and_then(|n| n.as_str())
                            .unwrap_or("")
                            .to_string();
                        let arguments = block
                            .get("input")
                            .cloned()
                            .unwrap_or(serde_json::Value::Null);
                        tool_calls.push(ToolCall {
                            tool_name: name,
                            arguments,
                        });
                    }
                    _ => {}
                }
            }
        }

        let usage = body.get("usage").map(|u| TokenUsage {
            prompt_tokens: u.get("input_tokens").and_then(|v| v.as_u64()).unwrap_or(0) as u32,
            completion_tokens: u.get("output_tokens").and_then(|v| v.as_u64()).unwrap_or(0) as u32,
        });

        Ok(ChatResponse {
            content,
            tool_calls,
            usage,
        })
    }
}

fn claude_role(role: &ChatRole) -> &'static str {
    match role {
        ChatRole::User => "user",
        ChatRole::Assistant => "assistant",
        ChatRole::Tool => "user",
        ChatRole::System => "user", // should not reach here
    }
}

#[async_trait]
impl Provider for ClaudeProvider {
    fn name(&self) -> &str {
        "claude"
    }

    fn capabilities(&self) -> ProviderCapabilities {
        ProviderCapabilities {
            native_tool_calling: true,
            vision: true,
            streaming: true,
        }
    }

    async fn chat(&self, request: ChatRequest) -> anyhow::Result<ChatResponse> {
        let url = format!("{}/v1/messages", self.base_url());
        let body = self.build_request_body(&request, None);

        let resp = self
            .client
            .post(&url)
            .header("x-api-key", &self.config.api_key)
            .header("anthropic-version", "2023-06-01")
            .header("content-type", "application/json")
            .json(&body)
            .send()
            .await?;

        let status = resp.status();
        let resp_body: serde_json::Value = resp.json().await?;

        if !status.is_success() {
            let msg = resp_body
                .get("error")
                .and_then(|e| e.get("message"))
                .and_then(|m| m.as_str())
                .unwrap_or("unknown error");
            anyhow::bail!("Claude API error ({}): {}", status, msg);
        }

        Self::parse_response(&resp_body)
    }

    async fn chat_with_tools(
        &self,
        request: ChatRequest,
        tools: &[ToolSpec],
    ) -> anyhow::Result<ChatResponse> {
        let url = format!("{}/v1/messages", self.base_url());
        let body = self.build_request_body(&request, Some(tools));

        let resp = self
            .client
            .post(&url)
            .header("x-api-key", &self.config.api_key)
            .header("anthropic-version", "2023-06-01")
            .header("content-type", "application/json")
            .json(&body)
            .send()
            .await?;

        let status = resp.status();
        let resp_body: serde_json::Value = resp.json().await?;

        if !status.is_success() {
            let msg = resp_body
                .get("error")
                .and_then(|e| e.get("message"))
                .and_then(|m| m.as_str())
                .unwrap_or("unknown error");
            anyhow::bail!("Claude API error ({}): {}", status, msg);
        }

        Self::parse_response(&resp_body)
    }
}

// ---------------------------------------------------------------------------
// OpenAI Provider
// ---------------------------------------------------------------------------

/// OpenAI Chat Completions provider. Also supports Codex, Azure OpenAI,
/// and other compatible endpoints via `base_url` override.
pub struct OpenAIProvider {
    pub config: OpenAIConfig,
    client: reqwest::Client,
}

impl std::fmt::Debug for OpenAIProvider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("OpenAIProvider")
            .field("model", &self.config.model)
            .finish()
    }
}

impl OpenAIProvider {
    /// Create a new OpenAI provider with the given config.
    pub fn new(config: OpenAIConfig) -> Self {
        Self {
            config,
            client: reqwest::Client::new(),
        }
    }

    /// Create an OpenAI provider from the `OPENAI_API_KEY` env var.
    pub fn from_env() -> Option<Self> {
        let api_key = std::env::var("OPENAI_API_KEY").ok()?;
        Some(Self::new(OpenAIConfig {
            api_key,
            model: "gpt-4o".to_string(),
            base_url: None,
        }))
    }

    fn base_url(&self) -> &str {
        self.config
            .base_url
            .as_deref()
            .unwrap_or("https://api.openai.com")
    }

    /// Build the OpenAI Chat Completions API request body.
    fn build_request_body(
        &self,
        request: &ChatRequest,
        tools: Option<&[ToolSpec]>,
    ) -> serde_json::Value {
        let messages: Vec<serde_json::Value> = request
            .messages
            .iter()
            .map(|m| {
                serde_json::json!({
                    "role": openai_role(&m.role),
                    "content": m.content,
                })
            })
            .collect();

        let mut body = serde_json::json!({
            "model": request.model,
            "messages": messages,
        });

        if let Some(max_tokens) = request.max_tokens {
            body["max_tokens"] = serde_json::json!(max_tokens);
        }
        if let Some(temp) = request.temperature {
            body["temperature"] = serde_json::json!(temp);
        }
        if let Some(tool_specs) = tools {
            if !tool_specs.is_empty() {
                let tool_defs: Vec<serde_json::Value> = tool_specs
                    .iter()
                    .map(|t| {
                        serde_json::json!({
                            "type": "function",
                            "function": {
                                "name": t.name,
                                "description": t.description,
                                "parameters": t.parameters_schema,
                            }
                        })
                    })
                    .collect();
                body["tools"] = serde_json::Value::Array(tool_defs);
            }
        }

        body
    }

    /// Parse an OpenAI Chat Completions API response into a ChatResponse.
    fn parse_response(body: &serde_json::Value) -> anyhow::Result<ChatResponse> {
        let choice = body
            .get("choices")
            .and_then(|c| c.as_array())
            .and_then(|c| c.first())
            .ok_or_else(|| anyhow::anyhow!("no choices in OpenAI response"))?;

        let message = choice
            .get("message")
            .ok_or_else(|| anyhow::anyhow!("no message in choice"))?;

        let content = message
            .get("content")
            .and_then(|c| c.as_str())
            .unwrap_or("")
            .to_string();

        let mut tool_calls = Vec::new();
        if let Some(tc_array) = message.get("tool_calls").and_then(|tc| tc.as_array()) {
            for tc in tc_array {
                if let Some(func) = tc.get("function") {
                    let name = func
                        .get("name")
                        .and_then(|n| n.as_str())
                        .unwrap_or("")
                        .to_string();
                    let args_str = func
                        .get("arguments")
                        .and_then(|a| a.as_str())
                        .unwrap_or("{}");
                    let arguments: serde_json::Value =
                        serde_json::from_str(args_str).unwrap_or(serde_json::Value::Null);
                    tool_calls.push(ToolCall {
                        tool_name: name,
                        arguments,
                    });
                }
            }
        }

        let usage = body.get("usage").map(|u| TokenUsage {
            prompt_tokens: u.get("prompt_tokens").and_then(|v| v.as_u64()).unwrap_or(0) as u32,
            completion_tokens: u
                .get("completion_tokens")
                .and_then(|v| v.as_u64())
                .unwrap_or(0) as u32,
        });

        Ok(ChatResponse {
            content,
            tool_calls,
            usage,
        })
    }
}

fn openai_role(role: &ChatRole) -> &'static str {
    match role {
        ChatRole::System => "system",
        ChatRole::User => "user",
        ChatRole::Assistant => "assistant",
        ChatRole::Tool => "tool",
    }
}

#[async_trait]
impl Provider for OpenAIProvider {
    fn name(&self) -> &str {
        "openai"
    }

    fn capabilities(&self) -> ProviderCapabilities {
        ProviderCapabilities {
            native_tool_calling: true,
            vision: true,
            streaming: true,
        }
    }

    async fn chat(&self, request: ChatRequest) -> anyhow::Result<ChatResponse> {
        let url = format!("{}/v1/chat/completions", self.base_url());
        let body = self.build_request_body(&request, None);

        let resp = self
            .client
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.config.api_key))
            .header("content-type", "application/json")
            .json(&body)
            .send()
            .await?;

        let status = resp.status();
        let resp_body: serde_json::Value = resp.json().await?;

        if !status.is_success() {
            let msg = resp_body
                .get("error")
                .and_then(|e| e.get("message"))
                .and_then(|m| m.as_str())
                .unwrap_or("unknown error");
            anyhow::bail!("OpenAI API error ({}): {}", status, msg);
        }

        Self::parse_response(&resp_body)
    }

    async fn chat_with_tools(
        &self,
        request: ChatRequest,
        tools: &[ToolSpec],
    ) -> anyhow::Result<ChatResponse> {
        let url = format!("{}/v1/chat/completions", self.base_url());
        let body = self.build_request_body(&request, Some(tools));

        let resp = self
            .client
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.config.api_key))
            .header("content-type", "application/json")
            .json(&body)
            .send()
            .await?;

        let status = resp.status();
        let resp_body: serde_json::Value = resp.json().await?;

        if !status.is_success() {
            let msg = resp_body
                .get("error")
                .and_then(|e| e.get("message"))
                .and_then(|m| m.as_str())
                .unwrap_or("unknown error");
            anyhow::bail!("OpenAI API error ({}): {}", status, msg);
        }

        Self::parse_response(&resp_body)
    }
}

// ---------------------------------------------------------------------------
// Gemini Provider
// ---------------------------------------------------------------------------

/// Google Gemini provider using the Generative AI API.
pub struct GeminiProvider {
    pub config: GeminiConfig,
    client: reqwest::Client,
}

impl std::fmt::Debug for GeminiProvider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("GeminiProvider")
            .field("model", &self.config.model)
            .finish()
    }
}

impl GeminiProvider {
    /// Create a new Gemini provider with the given config.
    pub fn new(config: GeminiConfig) -> Self {
        Self {
            config,
            client: reqwest::Client::new(),
        }
    }

    /// Create a Gemini provider from the `GEMINI_API_KEY` env var.
    pub fn from_env() -> Option<Self> {
        let api_key = std::env::var("GEMINI_API_KEY").ok()?;
        Some(Self::new(GeminiConfig {
            api_key,
            model: "gemini-pro".to_string(),
        }))
    }

    /// Build the Gemini generateContent request body.
    fn build_request_body(
        &self,
        request: &ChatRequest,
        tools: Option<&[ToolSpec]>,
    ) -> serde_json::Value {
        let mut contents: Vec<serde_json::Value> = Vec::new();
        let mut system_instruction: Option<String> = None;

        for msg in &request.messages {
            match msg.role {
                ChatRole::System => {
                    system_instruction = Some(msg.content.clone());
                }
                _ => {
                    contents.push(serde_json::json!({
                        "role": gemini_role(&msg.role),
                        "parts": [{ "text": msg.content }],
                    }));
                }
            }
        }

        let mut body = serde_json::json!({
            "contents": contents,
        });

        if let Some(sys) = system_instruction {
            body["systemInstruction"] = serde_json::json!({
                "parts": [{ "text": sys }]
            });
        }

        // Generation config.
        let mut gen_config = serde_json::Map::new();
        if let Some(max_tokens) = request.max_tokens {
            gen_config.insert("maxOutputTokens".to_string(), serde_json::json!(max_tokens));
        }
        if let Some(temp) = request.temperature {
            gen_config.insert("temperature".to_string(), serde_json::json!(temp));
        }
        if !gen_config.is_empty() {
            body["generationConfig"] = serde_json::Value::Object(gen_config);
        }

        if let Some(tool_specs) = tools {
            if !tool_specs.is_empty() {
                let func_decls: Vec<serde_json::Value> = tool_specs
                    .iter()
                    .map(|t| {
                        serde_json::json!({
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.parameters_schema,
                        })
                    })
                    .collect();
                body["tools"] = serde_json::json!([{
                    "functionDeclarations": func_decls,
                }]);
            }
        }

        body
    }

    /// Parse a Gemini generateContent response into a ChatResponse.
    fn parse_response(body: &serde_json::Value) -> anyhow::Result<ChatResponse> {
        let mut content = String::new();
        let mut tool_calls = Vec::new();

        if let Some(candidates) = body.get("candidates").and_then(|c| c.as_array()) {
            if let Some(candidate) = candidates.first() {
                if let Some(parts) = candidate
                    .get("content")
                    .and_then(|c| c.get("parts"))
                    .and_then(|p| p.as_array())
                {
                    for part in parts {
                        if let Some(text) = part.get("text").and_then(|t| t.as_str()) {
                            content.push_str(text);
                        }
                        if let Some(fc) = part.get("functionCall") {
                            let name = fc
                                .get("name")
                                .and_then(|n| n.as_str())
                                .unwrap_or("")
                                .to_string();
                            let arguments =
                                fc.get("args").cloned().unwrap_or(serde_json::Value::Null);
                            tool_calls.push(ToolCall {
                                tool_name: name,
                                arguments,
                            });
                        }
                    }
                }
            }
        }

        let usage = body.get("usageMetadata").map(|u| TokenUsage {
            prompt_tokens: u
                .get("promptTokenCount")
                .and_then(|v| v.as_u64())
                .unwrap_or(0) as u32,
            completion_tokens: u
                .get("candidatesTokenCount")
                .and_then(|v| v.as_u64())
                .unwrap_or(0) as u32,
        });

        Ok(ChatResponse {
            content,
            tool_calls,
            usage,
        })
    }
}

fn gemini_role(role: &ChatRole) -> &'static str {
    match role {
        ChatRole::User | ChatRole::Tool => "user",
        ChatRole::Assistant => "model",
        ChatRole::System => "user", // should not reach here
    }
}

#[async_trait]
impl Provider for GeminiProvider {
    fn name(&self) -> &str {
        "gemini"
    }

    fn capabilities(&self) -> ProviderCapabilities {
        ProviderCapabilities {
            native_tool_calling: true,
            vision: true,
            streaming: true,
        }
    }

    async fn chat(&self, request: ChatRequest) -> anyhow::Result<ChatResponse> {
        let url = format!(
            "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}",
            request.model, self.config.api_key
        );
        let body = self.build_request_body(&request, None);

        let resp = self
            .client
            .post(&url)
            .header("content-type", "application/json")
            .json(&body)
            .send()
            .await?;

        let status = resp.status();
        let resp_body: serde_json::Value = resp.json().await?;

        if !status.is_success() {
            let msg = resp_body
                .get("error")
                .and_then(|e| e.get("message"))
                .and_then(|m| m.as_str())
                .unwrap_or("unknown error");
            anyhow::bail!("Gemini API error ({}): {}", status, msg);
        }

        Self::parse_response(&resp_body)
    }

    async fn chat_with_tools(
        &self,
        request: ChatRequest,
        tools: &[ToolSpec],
    ) -> anyhow::Result<ChatResponse> {
        let url = format!(
            "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}",
            request.model, self.config.api_key
        );
        let body = self.build_request_body(&request, Some(tools));

        let resp = self
            .client
            .post(&url)
            .header("content-type", "application/json")
            .json(&body)
            .send()
            .await?;

        let status = resp.status();
        let resp_body: serde_json::Value = resp.json().await?;

        if !status.is_success() {
            let msg = resp_body
                .get("error")
                .and_then(|e| e.get("message"))
                .and_then(|m| m.as_str())
                .unwrap_or("unknown error");
            anyhow::bail!("Gemini API error ({}): {}", status, msg);
        }

        Self::parse_response(&resp_body)
    }
}

// ---------------------------------------------------------------------------
// Ollama Provider
// ---------------------------------------------------------------------------

/// Ollama provider for local LLM inference.
pub struct OllamaProvider {
    pub config: OllamaConfig,
    client: reqwest::Client,
}

impl std::fmt::Debug for OllamaProvider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("OllamaProvider")
            .field("model", &self.config.model)
            .finish()
    }
}

impl OllamaProvider {
    /// Create a new Ollama provider with the given config.
    pub fn new(config: OllamaConfig) -> Self {
        Self {
            config,
            client: reqwest::Client::new(),
        }
    }

    /// Create an Ollama provider with default localhost settings.
    pub fn with_defaults() -> Self {
        Self::new(OllamaConfig {
            model: "llama3".to_string(),
            base_url: None,
        })
    }

    fn base_url(&self) -> &str {
        self.config
            .base_url
            .as_deref()
            .unwrap_or("http://localhost:11434")
    }

    /// Build the Ollama /api/chat request body.
    fn build_request_body(&self, request: &ChatRequest) -> serde_json::Value {
        let messages: Vec<serde_json::Value> = request
            .messages
            .iter()
            .map(|m| {
                serde_json::json!({
                    "role": ollama_role(&m.role),
                    "content": m.content,
                })
            })
            .collect();

        let mut body = serde_json::json!({
            "model": request.model,
            "messages": messages,
            "stream": false,
        });

        let mut options = serde_json::Map::new();
        if let Some(temp) = request.temperature {
            options.insert("temperature".to_string(), serde_json::json!(temp));
        }
        if let Some(max_tokens) = request.max_tokens {
            options.insert("num_predict".to_string(), serde_json::json!(max_tokens));
        }
        if !options.is_empty() {
            body["options"] = serde_json::Value::Object(options);
        }

        body
    }

    /// Parse an Ollama /api/chat response into a ChatResponse.
    fn parse_response(body: &serde_json::Value) -> anyhow::Result<ChatResponse> {
        let content = body
            .get("message")
            .and_then(|m| m.get("content"))
            .and_then(|c| c.as_str())
            .unwrap_or("")
            .to_string();

        // Ollama provides eval/prompt token counts at top level.
        let usage = if body.get("prompt_eval_count").is_some() || body.get("eval_count").is_some() {
            Some(TokenUsage {
                prompt_tokens: body
                    .get("prompt_eval_count")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0) as u32,
                completion_tokens: body.get("eval_count").and_then(|v| v.as_u64()).unwrap_or(0)
                    as u32,
            })
        } else {
            None
        };

        Ok(ChatResponse {
            content,
            tool_calls: vec![],
            usage,
        })
    }
}

fn ollama_role(role: &ChatRole) -> &'static str {
    match role {
        ChatRole::System => "system",
        ChatRole::User => "user",
        ChatRole::Assistant => "assistant",
        ChatRole::Tool => "user",
    }
}

#[async_trait]
impl Provider for OllamaProvider {
    fn name(&self) -> &str {
        "ollama"
    }

    fn capabilities(&self) -> ProviderCapabilities {
        ProviderCapabilities {
            native_tool_calling: false,
            vision: false,
            streaming: true,
        }
    }

    async fn chat(&self, request: ChatRequest) -> anyhow::Result<ChatResponse> {
        let url = format!("{}/api/chat", self.base_url());
        let body = self.build_request_body(&request);

        let resp = self
            .client
            .post(&url)
            .header("content-type", "application/json")
            .json(&body)
            .send()
            .await?;

        let status = resp.status();
        let resp_body: serde_json::Value = resp.json().await?;

        if !status.is_success() {
            let msg = resp_body
                .get("error")
                .and_then(|m| m.as_str())
                .unwrap_or("unknown error");
            anyhow::bail!("Ollama API error ({}): {}", status, msg);
        }

        Self::parse_response(&resp_body)
    }

    async fn chat_with_tools(
        &self,
        request: ChatRequest,
        _tools: &[ToolSpec],
    ) -> anyhow::Result<ChatResponse> {
        // Ollama does not natively support tool calling; delegate to plain chat.
        self.chat(request).await
    }
}

// ---------------------------------------------------------------------------
// Provider Registry
// ---------------------------------------------------------------------------

/// Registry that holds multiple provider implementations and provides
/// lookup by name or model-name routing.
pub struct ProviderRegistry {
    providers: Vec<Box<dyn Provider>>,
}

impl std::fmt::Debug for ProviderRegistry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let names: Vec<&str> = self.providers.iter().map(|p| p.name()).collect();
        f.debug_struct("ProviderRegistry")
            .field("providers", &names)
            .finish()
    }
}

impl ProviderRegistry {
    /// Create an empty registry.
    pub fn new() -> Self {
        Self {
            providers: Vec::new(),
        }
    }

    /// Register a provider.
    pub fn register(&mut self, provider: Box<dyn Provider>) {
        self.providers.push(provider);
    }

    /// Get a provider by its name.
    pub fn get(&self, name: &str) -> Option<&dyn Provider> {
        self.providers
            .iter()
            .find(|p| p.name() == name)
            .map(|p| &**p)
    }

    /// List all registered provider names.
    pub fn list(&self) -> Vec<&str> {
        self.providers.iter().map(|p| p.name()).collect()
    }

    /// Get the first registered provider (the "default").
    pub fn get_default(&self) -> Option<&dyn Provider> {
        self.providers.first().map(|p| &**p)
    }

    /// Route a model name to the appropriate provider.
    ///
    /// Uses prefix matching: model names starting with "claude" go to the
    /// claude provider, "gpt" or "o1" or "o3" to openai, "gemini" to gemini,
    /// and everything else to ollama (if registered).
    pub fn route(&self, model_name: &str) -> Option<&dyn Provider> {
        let lower = model_name.to_lowercase();
        let target = if lower.starts_with("claude") {
            "claude"
        } else if lower.starts_with("gpt")
            || lower.starts_with("o1")
            || lower.starts_with("o3")
            || lower.starts_with("o4")
            || lower.starts_with("chatgpt")
        {
            "openai"
        } else if lower.starts_with("gemini") {
            "gemini"
        } else {
            // Default to ollama for unknown model names (llama3, mistral, etc.)
            "ollama"
        };

        self.get(target)
    }

    /// Create a registry populated with all providers whose API keys are
    /// available in the environment.
    pub fn from_env() -> Self {
        let mut registry = Self::new();

        if let Some(claude) = ClaudeProvider::from_env() {
            registry.register(Box::new(claude));
        }
        if let Some(openai) = OpenAIProvider::from_env() {
            registry.register(Box::new(openai));
        }
        if let Some(gemini) = GeminiProvider::from_env() {
            registry.register(Box::new(gemini));
        }

        // Ollama is always available (local, no key needed).
        registry.register(Box::new(OllamaProvider::with_defaults()));

        registry
    }
}

impl Default for ProviderRegistry {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::provider::{ChatMessage, ChatRequest, ChatRole, StubProvider};
    use std::sync::Mutex;

    /// Mutex to serialize tests that mutate environment variables, since
    /// `std::env::set_var` / `remove_var` are process-global and tests run
    /// in parallel.
    static ENV_MUTEX: Mutex<()> = Mutex::new(());

    fn sample_request() -> ChatRequest {
        ChatRequest {
            model: "test-model".to_string(),
            messages: vec![ChatMessage {
                role: ChatRole::User,
                content: "Hello".to_string(),
            }],
            max_tokens: Some(100),
            temperature: Some(0.7),
        }
    }

    fn sample_request_with_system() -> ChatRequest {
        ChatRequest {
            model: "test-model".to_string(),
            messages: vec![
                ChatMessage {
                    role: ChatRole::System,
                    content: "You are helpful.".to_string(),
                },
                ChatMessage {
                    role: ChatRole::User,
                    content: "Hello".to_string(),
                },
            ],
            max_tokens: Some(100),
            temperature: None,
        }
    }

    fn sample_tool_spec() -> ToolSpec {
        ToolSpec {
            name: "get_weather".to_string(),
            description: "Get the weather for a location".to_string(),
            parameters_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "location": { "type": "string" }
                },
                "required": ["location"]
            }),
        }
    }

    // -----------------------------------------------------------------------
    // ProviderRegistry tests
    // -----------------------------------------------------------------------

    #[test]
    fn registry_new_is_empty() {
        let registry = ProviderRegistry::new();
        assert!(registry.list().is_empty());
        assert!(registry.get_default().is_none());
    }

    #[test]
    fn registry_register_and_get() {
        let mut registry = ProviderRegistry::new();
        registry.register(Box::new(StubProvider::default()));
        assert_eq!(registry.list().len(), 1);
        assert_eq!(registry.list()[0], "stub");
        assert!(registry.get("stub").is_some());
        assert!(registry.get("nonexistent").is_none());
    }

    #[test]
    fn registry_get_default_returns_first() {
        let mut registry = ProviderRegistry::new();
        registry.register(Box::new(StubProvider {
            response_text: "first".to_string(),
        }));
        let default = registry.get_default().unwrap();
        assert_eq!(default.name(), "stub");
    }

    #[test]
    fn registry_list_multiple() {
        let mut registry = ProviderRegistry::new();
        registry.register(Box::new(StubProvider::default()));
        registry.register(Box::new(OllamaProvider::with_defaults()));
        let names = registry.list();
        assert_eq!(names.len(), 2);
        assert!(names.contains(&"stub"));
        assert!(names.contains(&"ollama"));
    }

    #[test]
    fn registry_route_claude_models() {
        let mut registry = ProviderRegistry::new();
        registry.register(Box::new(ClaudeProvider::new(ClaudeConfig {
            api_key: "test".to_string(),
            model: "claude-sonnet-4-20250514".to_string(),
            base_url: None,
        })));
        assert!(registry.route("claude-3-opus").is_some());
        assert_eq!(registry.route("claude-3-opus").unwrap().name(), "claude");
        assert_eq!(
            registry.route("claude-sonnet-4-20250514").unwrap().name(),
            "claude"
        );
    }

    #[test]
    fn registry_route_openai_models() {
        let mut registry = ProviderRegistry::new();
        registry.register(Box::new(OpenAIProvider::new(OpenAIConfig {
            api_key: "test".to_string(),
            model: "gpt-4o".to_string(),
            base_url: None,
        })));
        assert_eq!(registry.route("gpt-4").unwrap().name(), "openai");
        assert_eq!(registry.route("gpt-4o").unwrap().name(), "openai");
        assert_eq!(registry.route("o1-preview").unwrap().name(), "openai");
        assert_eq!(registry.route("o3-mini").unwrap().name(), "openai");
        assert_eq!(
            registry.route("chatgpt-4o-latest").unwrap().name(),
            "openai"
        );
    }

    #[test]
    fn registry_route_gemini_models() {
        let mut registry = ProviderRegistry::new();
        registry.register(Box::new(GeminiProvider::new(GeminiConfig {
            api_key: "test".to_string(),
            model: "gemini-pro".to_string(),
        })));
        assert_eq!(registry.route("gemini-pro").unwrap().name(), "gemini");
        assert_eq!(registry.route("gemini-1.5-flash").unwrap().name(), "gemini");
    }

    #[test]
    fn registry_route_ollama_fallback() {
        let mut registry = ProviderRegistry::new();
        registry.register(Box::new(OllamaProvider::with_defaults()));
        assert_eq!(registry.route("llama3").unwrap().name(), "ollama");
        assert_eq!(registry.route("mistral").unwrap().name(), "ollama");
        assert_eq!(registry.route("codellama").unwrap().name(), "ollama");
    }

    #[test]
    fn registry_route_missing_provider_returns_none() {
        let registry = ProviderRegistry::new();
        assert!(registry.route("gpt-4").is_none());
    }

    #[test]
    fn registry_default_trait() {
        let registry = ProviderRegistry::default();
        assert!(registry.list().is_empty());
    }

    #[test]
    fn registry_debug_format() {
        let mut registry = ProviderRegistry::new();
        registry.register(Box::new(StubProvider::default()));
        let debug = format!("{:?}", registry);
        assert!(debug.contains("ProviderRegistry"));
        assert!(debug.contains("stub"));
    }

    // -----------------------------------------------------------------------
    // ClaudeProvider tests
    // -----------------------------------------------------------------------

    #[test]
    fn claude_config_serialization() {
        let config = ClaudeConfig {
            api_key: "sk-test".to_string(),
            model: "claude-sonnet-4-20250514".to_string(),
            base_url: None,
        };
        let json = serde_json::to_string(&config).unwrap();
        let round: ClaudeConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(round.model, "claude-sonnet-4-20250514");
    }

    #[test]
    fn claude_build_request_body_basic() {
        let provider = ClaudeProvider::new(ClaudeConfig {
            api_key: "test".to_string(),
            model: "claude-sonnet-4-20250514".to_string(),
            base_url: None,
        });
        let body = provider.build_request_body(&sample_request(), None);
        assert_eq!(body["model"], "test-model");
        assert!(body["messages"].is_array());
        assert_eq!(body["max_tokens"], 100);
        assert_eq!(body["temperature"], 0.7);
    }

    #[test]
    fn claude_build_request_extracts_system() {
        let provider = ClaudeProvider::new(ClaudeConfig {
            api_key: "test".to_string(),
            model: "claude-sonnet-4-20250514".to_string(),
            base_url: None,
        });
        let body = provider.build_request_body(&sample_request_with_system(), None);
        assert_eq!(body["system"], "You are helpful.");
        // System message should not appear in messages array.
        let messages = body["messages"].as_array().unwrap();
        assert_eq!(messages.len(), 1);
        assert_eq!(messages[0]["role"], "user");
    }

    #[test]
    fn claude_build_request_with_tools() {
        let provider = ClaudeProvider::new(ClaudeConfig {
            api_key: "test".to_string(),
            model: "claude-sonnet-4-20250514".to_string(),
            base_url: None,
        });
        let tools = vec![sample_tool_spec()];
        let body = provider.build_request_body(&sample_request(), Some(&tools));
        let tool_defs = body["tools"].as_array().unwrap();
        assert_eq!(tool_defs.len(), 1);
        assert_eq!(tool_defs[0]["name"], "get_weather");
        assert!(tool_defs[0]["input_schema"].is_object());
    }

    #[test]
    fn claude_parse_response_text() {
        let resp_json = serde_json::json!({
            "content": [
                { "type": "text", "text": "Hello, world!" }
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5
            }
        });
        let resp = ClaudeProvider::parse_response(&resp_json).unwrap();
        assert_eq!(resp.content, "Hello, world!");
        assert!(resp.tool_calls.is_empty());
        let usage = resp.usage.unwrap();
        assert_eq!(usage.prompt_tokens, 10);
        assert_eq!(usage.completion_tokens, 5);
    }

    #[test]
    fn claude_parse_response_tool_use() {
        let resp_json = serde_json::json!({
            "content": [
                { "type": "text", "text": "Let me check." },
                {
                    "type": "tool_use",
                    "name": "get_weather",
                    "input": { "location": "NYC" }
                }
            ],
            "usage": {
                "input_tokens": 20,
                "output_tokens": 15
            }
        });
        let resp = ClaudeProvider::parse_response(&resp_json).unwrap();
        assert_eq!(resp.content, "Let me check.");
        assert_eq!(resp.tool_calls.len(), 1);
        assert_eq!(resp.tool_calls[0].tool_name, "get_weather");
        assert_eq!(resp.tool_calls[0].arguments["location"], "NYC");
    }

    #[test]
    fn claude_capabilities() {
        let provider = ClaudeProvider::new(ClaudeConfig {
            api_key: "test".to_string(),
            model: "claude-sonnet-4-20250514".to_string(),
            base_url: None,
        });
        let caps = provider.capabilities();
        assert!(caps.native_tool_calling);
        assert!(caps.vision);
        assert!(caps.streaming);
    }

    #[test]
    fn claude_name() {
        let provider = ClaudeProvider::new(ClaudeConfig {
            api_key: "test".to_string(),
            model: "claude-sonnet-4-20250514".to_string(),
            base_url: None,
        });
        assert_eq!(provider.name(), "claude");
    }

    #[test]
    fn claude_custom_base_url() {
        let provider = ClaudeProvider::new(ClaudeConfig {
            api_key: "test".to_string(),
            model: "claude-sonnet-4-20250514".to_string(),
            base_url: Some("https://custom.api.com".to_string()),
        });
        assert_eq!(provider.base_url(), "https://custom.api.com");
    }

    #[test]
    fn claude_from_env_with_key() {
        let _lock = ENV_MUTEX.lock().unwrap();
        std::env::set_var("ANTHROPIC_API_KEY", "test-key-123");
        let provider = ClaudeProvider::from_env();
        assert!(provider.is_some());
        assert_eq!(provider.unwrap().config.api_key, "test-key-123");
        std::env::remove_var("ANTHROPIC_API_KEY");
    }

    #[test]
    fn claude_from_env_without_key() {
        let _lock = ENV_MUTEX.lock().unwrap();
        std::env::remove_var("ANTHROPIC_API_KEY");
        let provider = ClaudeProvider::from_env();
        assert!(provider.is_none());
    }

    // -----------------------------------------------------------------------
    // OpenAI Provider tests
    // -----------------------------------------------------------------------

    #[test]
    fn openai_config_serialization() {
        let config = OpenAIConfig {
            api_key: "sk-test".to_string(),
            model: "gpt-4o".to_string(),
            base_url: None,
        };
        let json = serde_json::to_string(&config).unwrap();
        let round: OpenAIConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(round.model, "gpt-4o");
    }

    #[test]
    fn openai_build_request_body_basic() {
        let provider = OpenAIProvider::new(OpenAIConfig {
            api_key: "test".to_string(),
            model: "gpt-4o".to_string(),
            base_url: None,
        });
        let body = provider.build_request_body(&sample_request(), None);
        assert_eq!(body["model"], "test-model");
        assert!(body["messages"].is_array());
        assert_eq!(body["max_tokens"], 100);
        assert_eq!(body["temperature"], 0.7);
    }

    #[test]
    fn openai_build_request_preserves_system_role() {
        let provider = OpenAIProvider::new(OpenAIConfig {
            api_key: "test".to_string(),
            model: "gpt-4o".to_string(),
            base_url: None,
        });
        let body = provider.build_request_body(&sample_request_with_system(), None);
        let messages = body["messages"].as_array().unwrap();
        assert_eq!(messages.len(), 2);
        assert_eq!(messages[0]["role"], "system");
        assert_eq!(messages[1]["role"], "user");
    }

    #[test]
    fn openai_build_request_with_tools() {
        let provider = OpenAIProvider::new(OpenAIConfig {
            api_key: "test".to_string(),
            model: "gpt-4o".to_string(),
            base_url: None,
        });
        let tools = vec![sample_tool_spec()];
        let body = provider.build_request_body(&sample_request(), Some(&tools));
        let tool_defs = body["tools"].as_array().unwrap();
        assert_eq!(tool_defs.len(), 1);
        assert_eq!(tool_defs[0]["type"], "function");
        assert_eq!(tool_defs[0]["function"]["name"], "get_weather");
    }

    #[test]
    fn openai_parse_response_text() {
        let resp_json = serde_json::json!({
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Hello from GPT!"
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5
            }
        });
        let resp = OpenAIProvider::parse_response(&resp_json).unwrap();
        assert_eq!(resp.content, "Hello from GPT!");
        assert!(resp.tool_calls.is_empty());
        let usage = resp.usage.unwrap();
        assert_eq!(usage.prompt_tokens, 10);
        assert_eq!(usage.completion_tokens, 5);
    }

    #[test]
    fn openai_parse_response_tool_calls() {
        let resp_json = serde_json::json!({
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": null,
                    "tool_calls": [{
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": "{\"location\":\"NYC\"}"
                        }
                    }]
                }
            }],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 15
            }
        });
        let resp = OpenAIProvider::parse_response(&resp_json).unwrap();
        assert_eq!(resp.content, "");
        assert_eq!(resp.tool_calls.len(), 1);
        assert_eq!(resp.tool_calls[0].tool_name, "get_weather");
        assert_eq!(resp.tool_calls[0].arguments["location"], "NYC");
    }

    #[test]
    fn openai_parse_response_no_choices_errors() {
        let resp_json = serde_json::json!({ "choices": [] });
        let result = OpenAIProvider::parse_response(&resp_json);
        assert!(result.is_err());
    }

    #[test]
    fn openai_capabilities() {
        let provider = OpenAIProvider::new(OpenAIConfig {
            api_key: "test".to_string(),
            model: "gpt-4o".to_string(),
            base_url: None,
        });
        let caps = provider.capabilities();
        assert!(caps.native_tool_calling);
        assert!(caps.vision);
        assert!(caps.streaming);
    }

    #[test]
    fn openai_custom_base_url() {
        let provider = OpenAIProvider::new(OpenAIConfig {
            api_key: "test".to_string(),
            model: "gpt-4o".to_string(),
            base_url: Some("https://my-azure.openai.azure.com".to_string()),
        });
        assert_eq!(provider.base_url(), "https://my-azure.openai.azure.com");
    }

    #[test]
    fn openai_from_env_with_key() {
        let _lock = ENV_MUTEX.lock().unwrap();
        std::env::set_var("OPENAI_API_KEY", "sk-openai-test");
        let provider = OpenAIProvider::from_env();
        assert!(provider.is_some());
        assert_eq!(provider.unwrap().config.api_key, "sk-openai-test");
        std::env::remove_var("OPENAI_API_KEY");
    }

    #[test]
    fn openai_from_env_without_key() {
        let _lock = ENV_MUTEX.lock().unwrap();
        std::env::remove_var("OPENAI_API_KEY");
        let provider = OpenAIProvider::from_env();
        assert!(provider.is_none());
    }

    // -----------------------------------------------------------------------
    // Gemini Provider tests
    // -----------------------------------------------------------------------

    #[test]
    fn gemini_config_serialization() {
        let config = GeminiConfig {
            api_key: "test-key".to_string(),
            model: "gemini-pro".to_string(),
        };
        let json = serde_json::to_string(&config).unwrap();
        let round: GeminiConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(round.model, "gemini-pro");
    }

    #[test]
    fn gemini_build_request_body_basic() {
        let provider = GeminiProvider::new(GeminiConfig {
            api_key: "test".to_string(),
            model: "gemini-pro".to_string(),
        });
        let body = provider.build_request_body(&sample_request(), None);
        assert!(body["contents"].is_array());
        let contents = body["contents"].as_array().unwrap();
        assert_eq!(contents.len(), 1);
        assert_eq!(contents[0]["role"], "user");
        assert_eq!(contents[0]["parts"][0]["text"], "Hello");
        assert_eq!(body["generationConfig"]["maxOutputTokens"], 100);
        assert_eq!(body["generationConfig"]["temperature"], 0.7);
    }

    #[test]
    fn gemini_build_request_extracts_system() {
        let provider = GeminiProvider::new(GeminiConfig {
            api_key: "test".to_string(),
            model: "gemini-pro".to_string(),
        });
        let body = provider.build_request_body(&sample_request_with_system(), None);
        let contents = body["contents"].as_array().unwrap();
        assert_eq!(contents.len(), 1);
        assert_eq!(
            body["systemInstruction"]["parts"][0]["text"],
            "You are helpful."
        );
    }

    #[test]
    fn gemini_build_request_with_tools() {
        let provider = GeminiProvider::new(GeminiConfig {
            api_key: "test".to_string(),
            model: "gemini-pro".to_string(),
        });
        let tools = vec![sample_tool_spec()];
        let body = provider.build_request_body(&sample_request(), Some(&tools));
        let tool_defs = body["tools"][0]["functionDeclarations"].as_array().unwrap();
        assert_eq!(tool_defs.len(), 1);
        assert_eq!(tool_defs[0]["name"], "get_weather");
    }

    #[test]
    fn gemini_parse_response_text() {
        let resp_json = serde_json::json!({
            "candidates": [{
                "content": {
                    "parts": [{ "text": "Hello from Gemini!" }],
                    "role": "model"
                }
            }],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5
            }
        });
        let resp = GeminiProvider::parse_response(&resp_json).unwrap();
        assert_eq!(resp.content, "Hello from Gemini!");
        assert!(resp.tool_calls.is_empty());
        let usage = resp.usage.unwrap();
        assert_eq!(usage.prompt_tokens, 10);
        assert_eq!(usage.completion_tokens, 5);
    }

    #[test]
    fn gemini_parse_response_function_call() {
        let resp_json = serde_json::json!({
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "get_weather",
                            "args": { "location": "NYC" }
                        }
                    }],
                    "role": "model"
                }
            }]
        });
        let resp = GeminiProvider::parse_response(&resp_json).unwrap();
        assert_eq!(resp.tool_calls.len(), 1);
        assert_eq!(resp.tool_calls[0].tool_name, "get_weather");
        assert_eq!(resp.tool_calls[0].arguments["location"], "NYC");
    }

    #[test]
    fn gemini_capabilities() {
        let provider = GeminiProvider::new(GeminiConfig {
            api_key: "test".to_string(),
            model: "gemini-pro".to_string(),
        });
        let caps = provider.capabilities();
        assert!(caps.native_tool_calling);
        assert!(caps.vision);
        assert!(caps.streaming);
    }

    #[test]
    fn gemini_from_env_with_key() {
        let _lock = ENV_MUTEX.lock().unwrap();
        std::env::set_var("GEMINI_API_KEY", "gemini-test-key");
        let provider = GeminiProvider::from_env();
        assert!(provider.is_some());
        assert_eq!(provider.unwrap().config.api_key, "gemini-test-key");
        std::env::remove_var("GEMINI_API_KEY");
    }

    #[test]
    fn gemini_from_env_without_key() {
        let _lock = ENV_MUTEX.lock().unwrap();
        std::env::remove_var("GEMINI_API_KEY");
        let provider = GeminiProvider::from_env();
        assert!(provider.is_none());
    }

    // -----------------------------------------------------------------------
    // Ollama Provider tests
    // -----------------------------------------------------------------------

    #[test]
    fn ollama_config_serialization() {
        let config = OllamaConfig {
            model: "llama3".to_string(),
            base_url: None,
        };
        let json = serde_json::to_string(&config).unwrap();
        let round: OllamaConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(round.model, "llama3");
    }

    #[test]
    fn ollama_build_request_body() {
        let provider = OllamaProvider::with_defaults();
        let body = provider.build_request_body(&sample_request());
        assert_eq!(body["model"], "test-model");
        assert_eq!(body["stream"], false);
        assert!(body["messages"].is_array());
        let options = &body["options"];
        assert_eq!(options["temperature"], 0.7);
        assert_eq!(options["num_predict"], 100);
    }

    #[test]
    fn ollama_parse_response_text() {
        let resp_json = serde_json::json!({
            "message": {
                "role": "assistant",
                "content": "Hello from Ollama!"
            },
            "prompt_eval_count": 10,
            "eval_count": 20
        });
        let resp = OllamaProvider::parse_response(&resp_json).unwrap();
        assert_eq!(resp.content, "Hello from Ollama!");
        assert!(resp.tool_calls.is_empty());
        let usage = resp.usage.unwrap();
        assert_eq!(usage.prompt_tokens, 10);
        assert_eq!(usage.completion_tokens, 20);
    }

    #[test]
    fn ollama_parse_response_no_usage() {
        let resp_json = serde_json::json!({
            "message": {
                "role": "assistant",
                "content": "Hi"
            }
        });
        let resp = OllamaProvider::parse_response(&resp_json).unwrap();
        assert_eq!(resp.content, "Hi");
        assert!(resp.usage.is_none());
    }

    #[test]
    fn ollama_capabilities() {
        let provider = OllamaProvider::with_defaults();
        let caps = provider.capabilities();
        assert!(!caps.native_tool_calling);
        assert!(!caps.vision);
        assert!(caps.streaming);
    }

    #[test]
    fn ollama_default_base_url() {
        let provider = OllamaProvider::with_defaults();
        assert_eq!(provider.base_url(), "http://localhost:11434");
    }

    #[test]
    fn ollama_custom_base_url() {
        let provider = OllamaProvider::new(OllamaConfig {
            model: "llama3".to_string(),
            base_url: Some("http://192.168.1.100:11434".to_string()),
        });
        assert_eq!(provider.base_url(), "http://192.168.1.100:11434");
    }

    #[test]
    fn ollama_name() {
        let provider = OllamaProvider::with_defaults();
        assert_eq!(provider.name(), "ollama");
    }

    // -----------------------------------------------------------------------
    // Role mapping tests
    // -----------------------------------------------------------------------

    #[test]
    fn claude_role_mapping() {
        assert_eq!(claude_role(&ChatRole::User), "user");
        assert_eq!(claude_role(&ChatRole::Assistant), "assistant");
        assert_eq!(claude_role(&ChatRole::Tool), "user");
        assert_eq!(claude_role(&ChatRole::System), "user");
    }

    #[test]
    fn openai_role_mapping() {
        assert_eq!(openai_role(&ChatRole::System), "system");
        assert_eq!(openai_role(&ChatRole::User), "user");
        assert_eq!(openai_role(&ChatRole::Assistant), "assistant");
        assert_eq!(openai_role(&ChatRole::Tool), "tool");
    }

    #[test]
    fn gemini_role_mapping() {
        assert_eq!(gemini_role(&ChatRole::User), "user");
        assert_eq!(gemini_role(&ChatRole::Assistant), "model");
        assert_eq!(gemini_role(&ChatRole::Tool), "user");
        assert_eq!(gemini_role(&ChatRole::System), "user");
    }

    #[test]
    fn ollama_role_mapping() {
        assert_eq!(ollama_role(&ChatRole::System), "system");
        assert_eq!(ollama_role(&ChatRole::User), "user");
        assert_eq!(ollama_role(&ChatRole::Assistant), "assistant");
        assert_eq!(ollama_role(&ChatRole::Tool), "user");
    }

    // -----------------------------------------------------------------------
    // from_env registry test
    // -----------------------------------------------------------------------

    #[test]
    fn registry_from_env_always_includes_ollama() {
        let _lock = ENV_MUTEX.lock().unwrap();
        // Clear all provider keys to ensure only ollama is registered.
        std::env::remove_var("ANTHROPIC_API_KEY");
        std::env::remove_var("OPENAI_API_KEY");
        std::env::remove_var("GEMINI_API_KEY");
        let registry = ProviderRegistry::from_env();
        let names = registry.list();
        assert!(names.contains(&"ollama"));
        // With no keys set, ollama should be the only provider.
        assert_eq!(names.len(), 1);
    }

    #[test]
    fn registry_from_env_with_all_keys() {
        let _lock = ENV_MUTEX.lock().unwrap();
        std::env::set_var("ANTHROPIC_API_KEY", "test-claude");
        std::env::set_var("OPENAI_API_KEY", "test-openai");
        std::env::set_var("GEMINI_API_KEY", "test-gemini");
        let registry = ProviderRegistry::from_env();
        let names = registry.list();
        assert!(names.contains(&"claude"));
        assert!(names.contains(&"openai"));
        assert!(names.contains(&"gemini"));
        assert!(names.contains(&"ollama"));
        assert_eq!(names.len(), 4);
        std::env::remove_var("ANTHROPIC_API_KEY");
        std::env::remove_var("OPENAI_API_KEY");
        std::env::remove_var("GEMINI_API_KEY");
    }
}

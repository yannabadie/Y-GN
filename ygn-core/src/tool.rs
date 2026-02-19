//! Tool trait, registry, and types.
//!
//! Defines the interface for executable tools and a registry to hold them,
//! based on ZeroClaw's Tool trait architecture.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Result of executing a tool.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
    pub success: bool,
    pub output: String,
    pub error: Option<String>,
}

/// Metadata describing a tool for discovery by providers.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolSpec {
    pub name: String,
    pub description: String,
    pub parameters_schema: serde_json::Value,
}

// ---------------------------------------------------------------------------
// Trait
// ---------------------------------------------------------------------------

/// Core trait every tool must implement.
#[async_trait]
pub trait Tool: Send + Sync {
    /// Unique name of the tool.
    fn name(&self) -> &str;

    /// Human-readable description.
    fn description(&self) -> &str;

    /// JSON Schema describing accepted parameters.
    fn parameters_schema(&self) -> serde_json::Value;

    /// Execute the tool with the given JSON arguments.
    async fn execute(&self, args: serde_json::Value) -> anyhow::Result<ToolResult>;

    /// Build a [`ToolSpec`] from this tool's metadata.
    fn spec(&self) -> ToolSpec {
        ToolSpec {
            name: self.name().to_string(),
            description: self.description().to_string(),
            parameters_schema: self.parameters_schema(),
        }
    }
}

// ---------------------------------------------------------------------------
// EchoTool (for integration testing / M3)
// ---------------------------------------------------------------------------

/// A tool that echoes its input back. Useful for smoke testing the tool
/// execution pipeline.
#[derive(Debug, Clone, Default)]
pub struct EchoTool;

#[async_trait]
impl Tool for EchoTool {
    fn name(&self) -> &str {
        "echo"
    }

    fn description(&self) -> &str {
        "Echoes the provided input back as output"
    }

    fn parameters_schema(&self) -> serde_json::Value {
        serde_json::json!({
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "Text to echo back"
                }
            },
            "required": ["input"]
        })
    }

    async fn execute(&self, args: serde_json::Value) -> anyhow::Result<ToolResult> {
        let input = args
            .get("input")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        Ok(ToolResult {
            success: true,
            output: input,
            error: None,
        })
    }
}

// ---------------------------------------------------------------------------
// ToolRegistry
// ---------------------------------------------------------------------------

/// Holds a collection of tools and provides lookup by name.
#[derive(Default)]
pub struct ToolRegistry {
    tools: Vec<Box<dyn Tool>>,
}

impl std::fmt::Debug for ToolRegistry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let names: Vec<&str> = self.tools.iter().map(|t| t.name()).collect();
        f.debug_struct("ToolRegistry")
            .field("tools", &names)
            .finish()
    }
}

impl ToolRegistry {
    /// Create an empty registry.
    pub fn new() -> Self {
        Self::default()
    }

    /// Register a tool.
    pub fn register(&mut self, tool: Box<dyn Tool>) {
        self.tools.push(tool);
    }

    /// Get a tool by name.
    pub fn get(&self, name: &str) -> Option<&dyn Tool> {
        self.tools.iter().find(|t| t.name() == name).map(|t| &**t)
    }

    /// List all registered tool specs.
    pub fn list(&self) -> Vec<ToolSpec> {
        self.tools.iter().map(|t| t.spec()).collect()
    }

    /// Number of registered tools.
    pub fn len(&self) -> usize {
        self.tools.len()
    }

    /// Returns true if the registry is empty.
    pub fn is_empty(&self) -> bool {
        self.tools.is_empty()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn echo_tool_echoes_input() {
        let tool = EchoTool;
        let result = tool
            .execute(serde_json::json!({"input": "hello world"}))
            .await
            .unwrap();
        assert!(result.success);
        assert_eq!(result.output, "hello world");
        assert!(result.error.is_none());
    }

    #[tokio::test]
    async fn echo_tool_handles_missing_input() {
        let tool = EchoTool;
        let result = tool.execute(serde_json::json!({})).await.unwrap();
        assert!(result.success);
        assert_eq!(result.output, "");
    }

    #[test]
    fn echo_tool_spec() {
        let tool = EchoTool;
        let spec = tool.spec();
        assert_eq!(spec.name, "echo");
        assert!(!spec.description.is_empty());
    }

    #[test]
    fn registry_register_and_get() {
        let mut registry = ToolRegistry::new();
        assert!(registry.is_empty());

        registry.register(Box::new(EchoTool));
        assert_eq!(registry.len(), 1);

        let found = registry.get("echo");
        assert!(found.is_some());
        assert_eq!(found.unwrap().name(), "echo");
    }

    #[test]
    fn registry_list_tools() {
        let mut registry = ToolRegistry::new();
        registry.register(Box::new(EchoTool));

        let specs = registry.list();
        assert_eq!(specs.len(), 1);
        assert_eq!(specs[0].name, "echo");
    }

    #[test]
    fn registry_get_missing_returns_none() {
        let registry = ToolRegistry::new();
        assert!(registry.get("nonexistent").is_none());
    }

    #[test]
    fn tool_result_serialization() {
        let result = ToolResult {
            success: true,
            output: "ok".to_string(),
            error: None,
        };
        let json = serde_json::to_string(&result).unwrap();
        let round: ToolResult = serde_json::from_str(&json).unwrap();
        assert!(round.success);
        assert_eq!(round.output, "ok");
    }
}

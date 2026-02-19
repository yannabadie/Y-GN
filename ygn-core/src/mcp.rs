//! Minimal MCP (Model Context Protocol) server for Brain-Core integration.
//!
//! Implements a JSON-RPC 2.0 server over stdio (newline-delimited messages)
//! that exposes the tool registry to external clients such as ygn-brain.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::io::{self, BufRead, Write};

use crate::audit::{AuditEntry, AuditEventType, AuditLog};
use crate::policy::{PolicyAction, PolicyEngine};
use crate::tool::{EchoTool, ToolRegistry};

// ---------------------------------------------------------------------------
// JSON-RPC 2.0 types
// ---------------------------------------------------------------------------

/// Incoming JSON-RPC request (may be a notification if `id` is absent).
#[derive(Debug, Deserialize)]
struct JsonRpcRequest {
    #[allow(dead_code)]
    jsonrpc: String,
    id: Option<Value>,
    method: String,
    #[serde(default)]
    params: Value,
}

/// Outgoing JSON-RPC success response.
#[derive(Debug, Serialize)]
struct JsonRpcResponse {
    jsonrpc: String,
    id: Value,
    result: Value,
}

/// Outgoing JSON-RPC error response.
#[derive(Debug, Serialize)]
struct JsonRpcErrorResponse {
    jsonrpc: String,
    id: Value,
    error: JsonRpcError,
}

#[derive(Debug, Serialize)]
struct JsonRpcError {
    code: i64,
    message: String,
}

// Standard JSON-RPC error codes
const METHOD_NOT_FOUND: i64 = -32601;
const INVALID_PARAMS: i64 = -32602;

// Custom error codes for policy enforcement
/// The tool call was denied by the security policy engine.
const POLICY_DENIED: i64 = -32001;
/// The tool call requires explicit user approval before it can proceed.
const APPROVAL_REQUIRED: i64 = -32002;

// ---------------------------------------------------------------------------
// McpServer
// ---------------------------------------------------------------------------

/// A minimal MCP server that routes JSON-RPC messages to a [`ToolRegistry`].
///
/// When a [`PolicyEngine`] is attached, every `tools/call` request is
/// evaluated before execution.  Denied calls produce a JSON-RPC error with
/// code [`POLICY_DENIED`]; calls that need approval use [`APPROVAL_REQUIRED`].
pub struct McpServer {
    registry: ToolRegistry,
    policy: Option<PolicyEngine>,
    audit_log: std::cell::RefCell<AuditLog>,
}

impl McpServer {
    /// Create a new MCP server with a pre-populated tool registry and no
    /// policy engine.
    pub fn new(registry: ToolRegistry) -> Self {
        Self {
            registry,
            policy: None,
            audit_log: std::cell::RefCell::new(AuditLog::new()),
        }
    }

    /// Create a new MCP server with a policy engine attached.
    pub fn with_policy(registry: ToolRegistry, policy: PolicyEngine) -> Self {
        Self {
            registry,
            policy: Some(policy),
            audit_log: std::cell::RefCell::new(AuditLog::new()),
        }
    }

    /// Create a server with the default set of built-in tools.
    pub fn with_default_tools() -> Self {
        let mut registry = ToolRegistry::new();
        registry.register(Box::new(EchoTool));
        Self::new(registry)
    }

    /// Access the audit log (e.g. for export after a session).
    pub fn audit_log(&self) -> std::cell::Ref<'_, AuditLog> {
        self.audit_log.borrow()
    }

    // -- public entry point ------------------------------------------------

    /// Parse a single JSON-RPC line and return an optional response.
    ///
    /// Returns `None` for notifications (messages without an `id`).
    pub fn handle_message(&self, line: &str) -> Option<String> {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            return None;
        }

        let req: JsonRpcRequest = match serde_json::from_str(trimmed) {
            Ok(r) => r,
            Err(e) => {
                // Parse error — respond with null id per JSON-RPC spec.
                let err = JsonRpcErrorResponse {
                    jsonrpc: "2.0".into(),
                    id: Value::Null,
                    error: JsonRpcError {
                        code: -32700,
                        message: format!("Parse error: {e}"),
                    },
                };
                return Some(serde_json::to_string(&err).unwrap());
            }
        };

        // Notifications have no id — acknowledge silently.
        let id = req.id?;

        let result = match req.method.as_str() {
            "initialize" => self.handle_initialize(),
            "tools/list" => self.handle_tools_list(),
            "tools/call" => self.handle_tools_call(&req.params),
            _ => Err((
                METHOD_NOT_FOUND,
                format!("Method not found: {}", req.method),
            )),
        };

        let response_json = match result {
            Ok(value) => serde_json::to_string(&JsonRpcResponse {
                jsonrpc: "2.0".into(),
                id,
                result: value,
            })
            .unwrap(),
            Err((code, message)) => serde_json::to_string(&JsonRpcErrorResponse {
                jsonrpc: "2.0".into(),
                id,
                error: JsonRpcError { code, message },
            })
            .unwrap(),
        };

        Some(response_json)
    }

    /// Run the MCP server over stdio, reading newline-delimited JSON-RPC
    /// messages from stdin and writing responses to stdout.
    pub fn run_stdio(&self) -> io::Result<()> {
        let stdin = io::stdin();
        let mut stdout = io::stdout();

        // Log to stderr so we never pollute the JSON-RPC channel.
        eprintln!("ygn-core MCP server started (stdio mode)");

        for line in stdin.lock().lines() {
            let line = line?;
            if let Some(response) = self.handle_message(&line) {
                writeln!(stdout, "{response}")?;
                stdout.flush()?;
            }
        }

        eprintln!("ygn-core MCP server shutting down");
        Ok(())
    }

    // -- method handlers ---------------------------------------------------

    fn handle_initialize(&self) -> Result<Value, (i64, String)> {
        Ok(json!({
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "ygn-core",
                "version": env!("CARGO_PKG_VERSION")
            }
        }))
    }

    fn handle_tools_list(&self) -> Result<Value, (i64, String)> {
        let tools: Vec<Value> = self
            .registry
            .list()
            .iter()
            .map(|spec| {
                json!({
                    "name": spec.name,
                    "description": spec.description,
                    "inputSchema": spec.parameters_schema
                })
            })
            .collect();

        Ok(json!({ "tools": tools }))
    }

    fn handle_tools_call(&self, params: &Value) -> Result<Value, (i64, String)> {
        let name = params.get("name").and_then(|v| v.as_str()).ok_or_else(|| {
            (
                INVALID_PARAMS,
                "Missing required parameter: name".to_string(),
            )
        })?;

        let arguments = params
            .get("arguments")
            .cloned()
            .unwrap_or_else(|| json!({}));

        // --- Policy check (if a policy engine is attached) ----------------
        if let Some(ref policy) = self.policy {
            let decision = policy.evaluate(name, &arguments);

            // Record the attempt in the audit log.
            self.audit_log.borrow_mut().record(AuditEntry::now(
                AuditEventType::ToolCallAttempt,
                name,
                format!("{:?}", decision.action),
                format!("{:?}", decision.risk_level),
                json!({ "arguments": arguments }),
            ));

            match decision.action {
                PolicyAction::Deny => {
                    self.audit_log.borrow_mut().record(AuditEntry::now(
                        AuditEventType::AccessDenied,
                        name,
                        "Deny",
                        format!("{:?}", decision.risk_level),
                        json!({ "reason": decision.reason }),
                    ));
                    return Err((POLICY_DENIED, decision.reason));
                }
                PolicyAction::RequireApproval => {
                    self.audit_log.borrow_mut().record(AuditEntry::now(
                        AuditEventType::ApprovalRequired,
                        name,
                        "RequireApproval",
                        format!("{:?}", decision.risk_level),
                        json!({ "reason": decision.reason }),
                    ));
                    return Err((APPROVAL_REQUIRED, decision.reason));
                }
                PolicyAction::Allow => {
                    self.audit_log.borrow_mut().record(AuditEntry::now(
                        AuditEventType::AccessGranted,
                        name,
                        "Allow",
                        format!("{:?}", decision.risk_level),
                        json!({ "reason": decision.reason }),
                    ));
                }
            }
        }

        let tool = self
            .registry
            .get(name)
            .ok_or_else(|| (INVALID_PARAMS, format!("Tool not found: {name}")))?;

        // Run the async tool execution inside a blocking tokio runtime.
        let rt = tokio::runtime::Runtime::new()
            .map_err(|e| (INVALID_PARAMS, format!("Runtime error: {e}")))?;

        let result = rt
            .block_on(tool.execute(arguments))
            .map_err(|e| (INVALID_PARAMS, format!("Tool execution error: {e}")))?;

        if result.success {
            Ok(json!({
                "content": [{
                    "type": "text",
                    "text": result.output
                }]
            }))
        } else {
            Ok(json!({
                "content": [{
                    "type": "text",
                    "text": result.error.unwrap_or_else(|| "Unknown error".into())
                }],
                "isError": true
            }))
        }
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    /// Helper: create a server with default (echo) tools.
    fn server() -> McpServer {
        McpServer::with_default_tools()
    }

    /// Helper: parse JSON-RPC response into a Value.
    fn parse_response(raw: &str) -> Value {
        serde_json::from_str(raw).expect("response must be valid JSON")
    }

    // -- initialize --------------------------------------------------------

    #[test]
    fn initialize_returns_capabilities() {
        let srv = server();
        let req = r#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"ygn-brain","version":"0.1.0"}}}"#;
        let resp = srv.handle_message(req).expect("should produce a response");
        let v = parse_response(&resp);

        assert_eq!(v["jsonrpc"], "2.0");
        assert_eq!(v["id"], 1);
        assert_eq!(v["result"]["protocolVersion"], "2024-11-05");
        assert!(v["result"]["capabilities"]["tools"].is_object());
        assert_eq!(v["result"]["serverInfo"]["name"], "ygn-core");
    }

    // -- notifications (no id) produce no response -------------------------

    #[test]
    fn notification_produces_no_response() {
        let srv = server();
        let req = r#"{"jsonrpc":"2.0","method":"notifications/initialized"}"#;
        assert!(srv.handle_message(req).is_none());
    }

    // -- tools/list --------------------------------------------------------

    #[test]
    fn tools_list_returns_echo_tool() {
        let srv = server();
        let req = r#"{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}"#;
        let resp = srv.handle_message(req).expect("should produce a response");
        let v = parse_response(&resp);

        assert_eq!(v["id"], 2);
        let tools = v["result"]["tools"].as_array().expect("tools array");
        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0]["name"], "echo");
        assert!(tools[0]["inputSchema"]["properties"]["input"].is_object());
    }

    // -- tools/call echo ---------------------------------------------------

    #[test]
    fn tools_call_echo_returns_text() {
        let srv = server();
        let req = r#"{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"echo","arguments":{"input":"hello world"}}}"#;
        let resp = srv.handle_message(req).expect("should produce a response");
        let v = parse_response(&resp);

        assert_eq!(v["id"], 3);
        let content = v["result"]["content"].as_array().expect("content array");
        assert_eq!(content.len(), 1);
        assert_eq!(content[0]["type"], "text");
        assert_eq!(content[0]["text"], "hello world");
    }

    // -- unknown method → error -------------------------------------------

    #[test]
    fn unknown_method_returns_error() {
        let srv = server();
        let req = r#"{"jsonrpc":"2.0","id":4,"method":"bogus/method","params":{}}"#;
        let resp = srv.handle_message(req).expect("should produce a response");
        let v = parse_response(&resp);

        assert_eq!(v["id"], 4);
        assert_eq!(v["error"]["code"], METHOD_NOT_FOUND);
        assert!(v["error"]["message"]
            .as_str()
            .unwrap()
            .contains("Method not found"));
    }

    // -- unknown tool → error ---------------------------------------------

    #[test]
    fn unknown_tool_returns_error() {
        let srv = server();
        let req = r#"{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"nonexistent","arguments":{}}}"#;
        let resp = srv.handle_message(req).expect("should produce a response");
        let v = parse_response(&resp);

        assert_eq!(v["id"], 5);
        assert_eq!(v["error"]["code"], INVALID_PARAMS);
        assert!(v["error"]["message"]
            .as_str()
            .unwrap()
            .contains("Tool not found"));
    }

    // -- missing tool name in params → error ------------------------------

    #[test]
    fn tools_call_missing_name_returns_error() {
        let srv = server();
        let req = r#"{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{}}"#;
        let resp = srv.handle_message(req).expect("should produce a response");
        let v = parse_response(&resp);

        assert_eq!(v["id"], 6);
        assert_eq!(v["error"]["code"], INVALID_PARAMS);
        assert!(v["error"]["message"]
            .as_str()
            .unwrap()
            .contains("Missing required parameter"));
    }

    // -- malformed JSON → parse error -------------------------------------

    #[test]
    fn malformed_json_returns_parse_error() {
        let srv = server();
        let resp = srv
            .handle_message("this is not json")
            .expect("should produce error response");
        let v = parse_response(&resp);

        assert_eq!(v["id"], Value::Null);
        assert_eq!(v["error"]["code"], -32700);
    }

    // -- empty line → no response -----------------------------------------

    #[test]
    fn empty_line_produces_no_response() {
        let srv = server();
        assert!(srv.handle_message("").is_none());
        assert!(srv.handle_message("   ").is_none());
    }

    // -- tools/list with no params field ----------------------------------

    #[test]
    fn tools_list_without_params_field() {
        let srv = server();
        // The "params" field is omitted entirely — should still work.
        let req = r#"{"jsonrpc":"2.0","id":7,"method":"tools/list"}"#;
        let resp = srv.handle_message(req).expect("should produce a response");
        let v = parse_response(&resp);

        assert_eq!(v["id"], 7);
        let tools = v["result"]["tools"].as_array().expect("tools array");
        assert_eq!(tools.len(), 1);
    }

    // -- string id is preserved -------------------------------------------

    #[test]
    fn string_id_is_preserved() {
        let srv = server();
        let req = r#"{"jsonrpc":"2.0","id":"abc-123","method":"initialize","params":{}}"#;
        let resp = srv.handle_message(req).expect("should produce a response");
        let v = parse_response(&resp);

        assert_eq!(v["id"], "abc-123");
    }

    // -- policy-gated tool calls ------------------------------------------

    use crate::policy::PolicyEngine;
    use crate::sandbox::{ProcessSandbox, SandboxProfile};
    use std::time::Duration;

    /// Helper: build a server with a policy engine that denies "dangerous_tool".
    fn server_with_policy() -> McpServer {
        let mut registry = ToolRegistry::new();
        registry.register(Box::new(EchoTool));

        let sandbox = ProcessSandbox::new(SandboxProfile::Net);
        let policy = PolicyEngine::new(
            Box::new(sandbox),
            vec!["needs_approval".into()],
            vec!["dangerous_tool".into()],
            Duration::from_secs(30),
        );
        McpServer::with_policy(registry, policy)
    }

    #[test]
    fn policy_denied_tool_returns_error() {
        let srv = server_with_policy();
        let req = r#"{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"dangerous_tool","arguments":{}}}"#;
        let resp = srv.handle_message(req).expect("should produce a response");
        let v = parse_response(&resp);

        assert_eq!(v["error"]["code"], POLICY_DENIED);
        assert!(v["error"]["message"]
            .as_str()
            .unwrap()
            .contains("deny list"));
    }

    #[test]
    fn policy_approval_required_returns_error() {
        let srv = server_with_policy();
        let req = r#"{"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"needs_approval","arguments":{}}}"#;
        let resp = srv.handle_message(req).expect("should produce a response");
        let v = parse_response(&resp);

        assert_eq!(v["error"]["code"], APPROVAL_REQUIRED);
        assert!(v["error"]["message"].as_str().unwrap().contains("approval"));
    }

    #[test]
    fn policy_allowed_tool_executes() {
        let srv = server_with_policy();
        let req = r#"{"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"echo","arguments":{"input":"safe"}}}"#;
        let resp = srv.handle_message(req).expect("should produce a response");
        let v = parse_response(&resp);

        // Should succeed, not error.
        assert!(v["error"].is_null());
        let content = v["result"]["content"].as_array().expect("content array");
        assert_eq!(content[0]["text"], "safe");
    }

    #[test]
    fn policy_audit_log_records_events() {
        let srv = server_with_policy();

        // Fire a denied call.
        let req = r#"{"jsonrpc":"2.0","id":13,"method":"tools/call","params":{"name":"dangerous_tool","arguments":{}}}"#;
        srv.handle_message(req);

        // Fire an allowed call.
        let req2 = r#"{"jsonrpc":"2.0","id":14,"method":"tools/call","params":{"name":"echo","arguments":{"input":"hi"}}}"#;
        srv.handle_message(req2);

        let log = srv.audit_log();
        // Denied call: ToolCallAttempt + AccessDenied = 2
        // Allowed call: ToolCallAttempt + AccessGranted = 2
        assert!(
            log.len() >= 4,
            "Expected at least 4 audit entries, got {}",
            log.len()
        );
    }
}

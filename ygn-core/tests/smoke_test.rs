//! End-to-end smoke tests for ygn-core subsystems.
//!
//! These integration tests live in `tests/` (outside `src/`) and exercise
//! public APIs across module boundaries.

use std::time::Duration;

use chrono::Utc;
use serde_json::{json, Value};

use ygn_core::audit::AuditEventType;
use ygn_core::mcp::McpServer;
use ygn_core::policy::PolicyEngine;
use ygn_core::registry::{
    DiscoveryFilter, Endpoint, InMemoryRegistry, NodeInfo, NodeRegistry, NodeRole, TrustTier,
};
use ygn_core::sandbox::{ProcessSandbox, SandboxProfile};
use ygn_core::tool::{EchoTool, ToolRegistry};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Parse a JSON-RPC response string into a serde_json::Value.
fn parse_response(raw: &str) -> Value {
    serde_json::from_str(raw).expect("response must be valid JSON")
}

/// Build an MCP server with echo + hardware tools.
fn server_with_tools() -> McpServer {
    let mut registry = ToolRegistry::new();
    registry.register(Box::new(EchoTool));
    registry.register(Box::new(ygn_core::hardware::HardwareTool::new()));
    McpServer::new(registry)
}

/// Create a NodeInfo with sensible defaults.
fn make_node(id: &str, role: NodeRole, trust: TrustTier, caps: Vec<&str>) -> NodeInfo {
    NodeInfo {
        node_id: id.to_string(),
        role,
        endpoints: vec![Endpoint {
            protocol: "http".to_string(),
            address: "127.0.0.1:3000".to_string(),
        }],
        trust_tier: trust,
        capabilities: caps.into_iter().map(String::from).collect(),
        last_seen: Utc::now(),
        metadata: json!({}),
    }
}

// ---------------------------------------------------------------------------
// Test 1: MCP server handles protocol
// ---------------------------------------------------------------------------

#[test]
fn smoke_mcp_protocol() {
    let srv = server_with_tools();

    // 1. initialize -> verify capabilities
    let init_req = r#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke-test","version":"0.1.0"}}}"#;
    let resp = srv
        .handle_message(init_req)
        .expect("initialize should produce a response");
    let v = parse_response(&resp);
    assert_eq!(v["result"]["protocolVersion"], "2024-11-05");
    assert!(v["result"]["capabilities"]["tools"].is_object());
    assert_eq!(v["result"]["serverInfo"]["name"], "ygn-core");

    // 2. tools/list -> verify echo + hardware tools present
    let list_req = r#"{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}"#;
    let resp = srv
        .handle_message(list_req)
        .expect("tools/list should produce a response");
    let v = parse_response(&resp);
    let tools = v["result"]["tools"].as_array().expect("tools array");
    assert_eq!(tools.len(), 2, "Expected echo + hardware tools");
    let tool_names: Vec<&str> = tools.iter().map(|t| t["name"].as_str().unwrap()).collect();
    assert!(tool_names.contains(&"echo"), "echo tool should be present");
    assert!(
        tool_names.contains(&"hardware"),
        "hardware tool should be present"
    );

    // 3. tools/call echo -> verify echoed text
    let echo_req = r#"{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"echo","arguments":{"input":"smoke test"}}}"#;
    let resp = srv
        .handle_message(echo_req)
        .expect("tools/call echo should produce a response");
    let v = parse_response(&resp);
    let content = v["result"]["content"].as_array().expect("content array");
    assert_eq!(content[0]["type"], "text");
    assert_eq!(content[0]["text"], "smoke test");

    // 4. unknown method -> verify error
    let bad_req = r#"{"jsonrpc":"2.0","id":4,"method":"nonexistent/method","params":{}}"#;
    let resp = srv
        .handle_message(bad_req)
        .expect("unknown method should produce an error response");
    let v = parse_response(&resp);
    assert_eq!(v["error"]["code"], -32601);
    assert!(v["error"]["message"]
        .as_str()
        .unwrap()
        .contains("Method not found"));
}

// ---------------------------------------------------------------------------
// Test 2: Registry + discovery
// ---------------------------------------------------------------------------

#[tokio::test]
async fn smoke_registry_discovery() {
    let reg = InMemoryRegistry::new();

    // Register 3 nodes: Brain, Core, Edge
    let brain = make_node(
        "brain-1",
        NodeRole::Brain,
        TrustTier::Trusted,
        vec!["reasoning", "planning"],
    );
    let core = make_node(
        "core-1",
        NodeRole::Core,
        TrustTier::Trusted,
        vec!["echo", "hardware"],
    );
    let edge = make_node(
        "edge-1",
        NodeRole::Edge,
        TrustTier::Trusted,
        vec!["hardware", "sensor"],
    );

    reg.register(brain).await.unwrap();
    reg.register(core).await.unwrap();
    reg.register(edge).await.unwrap();

    // Discover by role -> correct count
    let brain_filter = DiscoveryFilter {
        role: Some(NodeRole::Brain),
        ..Default::default()
    };
    let brain_nodes = reg.discover(brain_filter).await.unwrap();
    assert_eq!(brain_nodes.len(), 1);
    assert_eq!(brain_nodes[0].node_id, "brain-1");

    // Discover by capability -> correct match
    let hw_filter = DiscoveryFilter {
        capability: Some("hardware".to_string()),
        ..Default::default()
    };
    let hw_nodes = reg.discover(hw_filter).await.unwrap();
    assert_eq!(
        hw_nodes.len(),
        2,
        "core-1 and edge-1 both have 'hardware' capability"
    );
    let hw_ids: Vec<&str> = hw_nodes.iter().map(|n| n.node_id.as_str()).collect();
    assert!(hw_ids.contains(&"core-1"));
    assert!(hw_ids.contains(&"edge-1"));

    // Heartbeat -> last_seen updates
    let before = reg.get("core-1").await.unwrap().unwrap().last_seen;
    // Small sleep to ensure timestamp difference
    tokio::time::sleep(Duration::from_millis(10)).await;
    reg.heartbeat("core-1").await.unwrap();
    let after = reg.get("core-1").await.unwrap().unwrap().last_seen;
    assert!(
        after > before,
        "Heartbeat should update last_seen timestamp"
    );
}

// ---------------------------------------------------------------------------
// Test 3: Policy + Audit trail
// ---------------------------------------------------------------------------

#[test]
fn smoke_policy_audit() {
    let sandbox = ProcessSandbox::new(SandboxProfile::Net);
    let policy = PolicyEngine::new(
        Box::new(sandbox),
        vec!["needs_approval".into()],
        vec!["rm_rf".into(), "drop_table".into()],
        Duration::from_secs(30),
    );

    // Evaluate a denied tool -> Deny
    let denied = policy.evaluate("rm_rf", &json!({}));
    assert_eq!(
        denied.action,
        ygn_core::policy::PolicyAction::Deny,
        "Denied tool should produce Deny"
    );

    // Evaluate a shell tool -> RequireApproval
    let shell = policy.evaluate("bash_exec", &json!({}));
    assert_eq!(
        shell.action,
        ygn_core::policy::PolicyAction::RequireApproval,
        "Shell tool should require approval"
    );

    // Evaluate a safe tool -> Allow
    let safe = policy.evaluate("echo", &json!({"input": "hello"}));
    assert_eq!(
        safe.action,
        ygn_core::policy::PolicyAction::Allow,
        "Safe tool should be allowed"
    );

    // Build an MCP server with this policy to test the audit log integration
    let mut registry = ToolRegistry::new();
    registry.register(Box::new(EchoTool));

    let sandbox2 = ProcessSandbox::new(SandboxProfile::Net);
    let policy2 = PolicyEngine::new(
        Box::new(sandbox2),
        vec!["needs_approval".into()],
        vec!["rm_rf".into()],
        Duration::from_secs(30),
    );
    let srv = McpServer::with_policy(registry, policy2);

    // Fire a denied call
    let deny_req = r#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"rm_rf","arguments":{}}}"#;
    srv.handle_message(deny_req);

    // Fire an approval-required call
    let approval_req = r#"{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"needs_approval","arguments":{}}}"#;
    srv.handle_message(approval_req);

    // Fire an allowed call
    let allow_req = r#"{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"echo","arguments":{"input":"safe"}}}"#;
    srv.handle_message(allow_req);

    // Check audit log has correct entries
    let log = srv.audit_log();
    // Denied: ToolCallAttempt + AccessDenied = 2
    // Approval: ToolCallAttempt + ApprovalRequired = 2
    // Allowed: ToolCallAttempt + AccessGranted = 2
    assert!(
        log.len() >= 6,
        "Expected at least 6 audit entries, got {}",
        log.len()
    );

    let entries = log.entries();

    // Verify denied events are present
    let denied_events: Vec<_> = entries
        .iter()
        .filter(|e| e.event_type == AuditEventType::AccessDenied)
        .collect();
    assert!(
        !denied_events.is_empty(),
        "Should have at least one AccessDenied event"
    );
    assert_eq!(denied_events[0].tool_name, "rm_rf");

    // Verify approval-required events are present
    let approval_events: Vec<_> = entries
        .iter()
        .filter(|e| e.event_type == AuditEventType::ApprovalRequired)
        .collect();
    assert!(
        !approval_events.is_empty(),
        "Should have at least one ApprovalRequired event"
    );

    // Verify allowed events are present
    let granted_events: Vec<_> = entries
        .iter()
        .filter(|e| e.event_type == AuditEventType::AccessGranted)
        .collect();
    assert!(
        !granted_events.is_empty(),
        "Should have at least one AccessGranted event"
    );
    assert_eq!(granted_events[0].tool_name, "echo");
}

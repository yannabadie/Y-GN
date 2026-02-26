use axum::{routing::{get, post}, Json, Router};
use serde_json::{json, Value};

use crate::a2a::{self, TaskStore};
use crate::mcp::McpServer;
use crate::multi_provider::ProviderRegistry;
use crate::provider_health::ProviderHealth;
use crate::registry::NodeRegistry;
use crate::sqlite_registry::SqliteRegistry;

async fn health() -> Json<Value> {
    Json(json!({
        "status": "ok",
        "service": "ygn-core",
        "version": env!("CARGO_PKG_VERSION")
    }))
}

/// `GET /providers` — List all configured providers from `ProviderRegistry::from_env()`.
async fn list_providers() -> Json<Value> {
    let registry = ProviderRegistry::from_env();
    let providers: Vec<Value> = registry
        .list()
        .iter()
        .map(|name| {
            let caps = registry
                .get(name)
                .map(|p| {
                    let c = p.capabilities();
                    json!({
                        "native_tool_calling": c.native_tool_calling,
                        "vision": c.vision,
                        "streaming": c.streaming,
                    })
                })
                .unwrap_or(json!(null));
            json!({
                "name": name,
                "capabilities": caps,
            })
        })
        .collect();

    Json(json!({
        "providers": providers,
        "count": providers.len(),
    }))
}

/// `GET /health/providers` — Health status summary for all providers.
async fn providers_health() -> Json<Value> {
    let registry = ProviderRegistry::from_env();
    let health = ProviderHealth::new();

    let statuses: Vec<Value> = registry
        .list()
        .iter()
        .map(|name| {
            let status = health.get_status(name);
            match status {
                Some(s) => json!({
                    "provider": s.provider,
                    "healthy": s.healthy,
                    "consecutive_failures": s.consecutive_failures,
                    "total_requests": s.total_requests,
                    "total_failures": s.total_failures,
                    "avg_latency_ms": s.avg_latency_ms,
                }),
                None => json!({
                    "provider": name,
                    "healthy": true,
                    "consecutive_failures": 0,
                    "total_requests": 0,
                    "total_failures": 0,
                    "avg_latency_ms": 0.0,
                }),
            }
        })
        .collect();

    let all_healthy = statuses
        .iter()
        .all(|s| s.get("healthy").and_then(|h| h.as_bool()).unwrap_or(false));

    Json(json!({
        "status": if all_healthy { "ok" } else { "degraded" },
        "providers": statuses,
    }))
}

// ---------------------------------------------------------------------------
// MCP over HTTP (Phase 6 — A4)
// ---------------------------------------------------------------------------

/// `POST /mcp` — JSON-RPC request via HTTP.
///
/// Accepts a JSON-RPC 2.0 request body, routes it through the same handler
/// used by the stdio MCP server.
async fn mcp_http(Json(body): Json<Value>) -> Json<Value> {
    let server = McpServer::with_default_tools();
    match server.handle_jsonrpc(body) {
        Some(response) => Json(response),
        None => Json(json!(null)),
    }
}

// ---------------------------------------------------------------------------
// A2A routes (Phase 7 — B2)
// ---------------------------------------------------------------------------

/// `GET /.well-known/agent.json` — Agent Card discovery.
async fn agent_card() -> Json<Value> {
    Json(a2a::agent_card())
}

/// `POST /a2a` — A2A message handler.
async fn a2a_handler(Json(body): Json<Value>) -> Json<Value> {
    let store = TaskStore::new();
    Json(a2a::handle_a2a(&body, &store))
}

// ---------------------------------------------------------------------------
// Registry routes
// ---------------------------------------------------------------------------

/// `GET /registry/nodes` — List all registered nodes.
async fn list_registry_nodes() -> Json<Value> {
    let registry = SqliteRegistry::new(":memory:").unwrap();
    // For now, returns an empty node list (no persisted state in this handler)
    // In production, registry would be shared state via Axum State
    let filter = crate::registry::DiscoveryFilter {
        role: None,
        trust_tier: None,
        capability: None,
        max_staleness_seconds: None,
    };
    let nodes = registry.discover(filter).await.unwrap_or_default();
    let node_values: Vec<Value> = nodes
        .iter()
        .map(|n| {
            json!({
                "node_id": n.node_id,
                "role": format!("{}", n.role),
                "trust_tier": format!("{}", n.trust_tier),
                "capabilities": n.capabilities,
                "last_seen": n.last_seen.to_rfc3339(),
            })
        })
        .collect();

    Json(json!({
        "nodes": node_values,
        "count": node_values.len(),
    }))
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

/// Build the full application router.
pub fn build_router() -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/providers", get(list_providers))
        .route("/health/providers", get(providers_health))
        .route("/mcp", post(mcp_http))
        .route("/.well-known/agent.json", get(agent_card))
        .route("/a2a", post(a2a_handler))
        .route("/registry/nodes", get(list_registry_nodes))
}

pub async fn run(bind: &str) -> anyhow::Result<()> {
    let app = build_router();

    let listener = tokio::net::TcpListener::bind(bind).await?;
    tracing::info!("ygn-core gateway listening on {bind}");
    axum::serve(listener, app).await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::{Request, StatusCode};
    use http_body_util::BodyExt;
    use tower::ServiceExt;

    /// Helper to build the test router with all routes.
    fn test_router() -> Router {
        build_router()
    }

    #[tokio::test]
    async fn health_returns_ok() {
        let app = test_router();
        let response = app
            .oneshot(
                Request::builder()
                    .uri("/health")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn providers_returns_ok_with_list() {
        let app = test_router();
        let response = app
            .oneshot(
                Request::builder()
                    .uri("/providers")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);

        let body = response.into_body().collect().await.unwrap().to_bytes();
        let json: Value = serde_json::from_slice(&body).unwrap();

        // Should have at least ollama (always registered).
        assert!(json["count"].as_u64().unwrap() >= 1);
        assert!(json["providers"].is_array());

        let providers = json["providers"].as_array().unwrap();
        let names: Vec<&str> = providers
            .iter()
            .filter_map(|p| p["name"].as_str())
            .collect();
        assert!(names.contains(&"ollama"));
    }

    #[tokio::test]
    async fn providers_include_capabilities() {
        let app = test_router();
        let response = app
            .oneshot(
                Request::builder()
                    .uri("/providers")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        let body = response.into_body().collect().await.unwrap().to_bytes();
        let json: Value = serde_json::from_slice(&body).unwrap();

        let providers = json["providers"].as_array().unwrap();
        for provider in providers {
            assert!(provider["capabilities"].is_object());
            assert!(provider["capabilities"]["streaming"].is_boolean());
        }
    }

    #[tokio::test]
    async fn health_providers_returns_ok() {
        let app = test_router();
        let response = app
            .oneshot(
                Request::builder()
                    .uri("/health/providers")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);

        let body = response.into_body().collect().await.unwrap().to_bytes();
        let json: Value = serde_json::from_slice(&body).unwrap();

        // Fresh health tracker — everything should be "ok".
        assert_eq!(json["status"], "ok");
        assert!(json["providers"].is_array());
    }

    #[tokio::test]
    async fn health_providers_shows_all_registered() {
        let app = test_router();
        let response = app
            .oneshot(
                Request::builder()
                    .uri("/health/providers")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        let body = response.into_body().collect().await.unwrap().to_bytes();
        let json: Value = serde_json::from_slice(&body).unwrap();

        let provider_statuses = json["providers"].as_array().unwrap();
        // At minimum, ollama should be listed.
        let names: Vec<&str> = provider_statuses
            .iter()
            .filter_map(|p| p["provider"].as_str())
            .collect();
        assert!(names.contains(&"ollama"));

        // All should be healthy with zero requests.
        for status in provider_statuses {
            assert_eq!(status["healthy"], true);
            assert_eq!(status["total_requests"], 0);
        }
    }

    // -----------------------------------------------------------------------
    // Phase 6: MCP over HTTP tests
    // -----------------------------------------------------------------------

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn mcp_http_echo_tool() {
        let app = test_router();
        let body = serde_json::to_string(&json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"input": "hello via http"}}
        }))
        .unwrap();

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/mcp")
                    .header("content-type", "application/json")
                    .body(Body::from(body))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);

        let bytes = response.into_body().collect().await.unwrap().to_bytes();
        let json: Value = serde_json::from_slice(&bytes).unwrap();
        let content = json["result"]["content"].as_array().unwrap();
        assert_eq!(content[0]["text"], "hello via http");
    }

    #[tokio::test]
    async fn mcp_http_tools_list() {
        let app = test_router();
        let body = serde_json::to_string(&json!({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }))
        .unwrap();

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/mcp")
                    .header("content-type", "application/json")
                    .body(Body::from(body))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);

        let bytes = response.into_body().collect().await.unwrap().to_bytes();
        let json: Value = serde_json::from_slice(&bytes).unwrap();
        let tools = json["result"]["tools"].as_array().unwrap();
        assert!(!tools.is_empty());
    }

    #[tokio::test]
    async fn mcp_http_invalid_method() {
        let app = test_router();
        let body = serde_json::to_string(&json!({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "bogus/method",
            "params": {}
        }))
        .unwrap();

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/mcp")
                    .header("content-type", "application/json")
                    .body(Body::from(body))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);

        let bytes = response.into_body().collect().await.unwrap().to_bytes();
        let json: Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(json["error"]["code"], -32601);
    }

    // -----------------------------------------------------------------------
    // Phase 7: A2A tests
    // -----------------------------------------------------------------------

    #[tokio::test]
    async fn agent_card_discovery() {
        let app = test_router();
        let response = app
            .oneshot(
                Request::builder()
                    .uri("/.well-known/agent.json")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);

        let bytes = response.into_body().collect().await.unwrap().to_bytes();
        let json: Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(json["name"], "Y-GN");
        assert!(json["skills"].as_array().unwrap().len() >= 3);
    }

    #[tokio::test]
    async fn a2a_send_message() {
        let app = test_router();
        let body = serde_json::to_string(&json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "SendMessage",
            "params": {"message": "Hello agent"}
        }))
        .unwrap();

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/a2a")
                    .header("content-type", "application/json")
                    .body(Body::from(body))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);

        let bytes = response.into_body().collect().await.unwrap().to_bytes();
        let json: Value = serde_json::from_slice(&bytes).unwrap();
        let task = &json["result"]["task"];
        assert!(!task["id"].as_str().unwrap().is_empty());
        assert_eq!(task["status"], "completed");
    }

    // -----------------------------------------------------------------------
    // Registry API tests
    // -----------------------------------------------------------------------

    #[tokio::test]
    async fn registry_nodes_returns_ok() {
        let app = test_router();
        let response = app
            .oneshot(
                Request::builder()
                    .uri("/registry/nodes")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);

        let body = response.into_body().collect().await.unwrap().to_bytes();
        let json: Value = serde_json::from_slice(&body).unwrap();
        assert!(json["nodes"].is_array());
        assert!(json["count"].is_number());
    }
}

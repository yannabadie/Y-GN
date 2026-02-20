use axum::{routing::get, Json, Router};
use serde_json::{json, Value};

use crate::multi_provider::ProviderRegistry;
use crate::provider_health::ProviderHealth;

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

/// Build the full application router.
pub fn build_router() -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/providers", get(list_providers))
        .route("/health/providers", get(providers_health))
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
}

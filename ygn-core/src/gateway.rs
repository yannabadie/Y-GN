use axum::{routing::get, Json, Router};
use serde_json::{json, Value};

async fn health() -> Json<Value> {
    Json(json!({
        "status": "ok",
        "service": "ygn-core",
        "version": env!("CARGO_PKG_VERSION")
    }))
}

pub async fn run(bind: &str) -> anyhow::Result<()> {
    let app = Router::new().route("/health", get(health));

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
    use tower::ServiceExt;

    #[tokio::test]
    async fn health_returns_ok() {
        let app = Router::new().route("/health", get(health));
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
}

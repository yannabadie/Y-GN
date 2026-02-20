//! Tunnel management — cloudflared, tailscale, and custom tunnel support.

use serde::{Deserialize, Serialize};

/// Supported tunnel providers.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TunnelProvider {
    Cloudflared,
    Tailscale,
    Ngrok,
    Custom,
}

/// Status of a tunnel.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TunnelStatus {
    Stopped,
    Starting,
    Running,
    Error,
}

/// Configuration for a tunnel.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TunnelConfig {
    pub provider: TunnelProvider,
    pub local_port: u16,
    pub subdomain: Option<String>,
    pub auth_token: Option<String>,
    pub extra_args: Vec<String>,
}

/// Information about an active tunnel.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TunnelInfo {
    pub id: String,
    pub provider: TunnelProvider,
    pub status: TunnelStatus,
    pub local_port: u16,
    pub public_url: Option<String>,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

/// Manages tunnel lifecycle.
#[derive(Debug, Default)]
pub struct TunnelManager {
    tunnels: Vec<TunnelInfo>,
}

impl TunnelManager {
    pub fn new() -> Self {
        Self { tunnels: vec![] }
    }

    /// Create a new tunnel (stub — does not actually spawn processes).
    pub fn create(&mut self, config: &TunnelConfig) -> anyhow::Result<TunnelInfo> {
        let id = uuid::Uuid::new_v4().to_string();
        let public_url = config.subdomain.as_ref().map(|s| match config.provider {
            TunnelProvider::Cloudflared => format!("https://{s}.trycloudflare.com"),
            TunnelProvider::Tailscale => format!("https://{s}.ts.net"),
            TunnelProvider::Ngrok => format!("https://{s}.ngrok.io"),
            TunnelProvider::Custom => format!("https://{s}"),
        });
        let info = TunnelInfo {
            id: id.clone(),
            provider: config.provider,
            status: TunnelStatus::Running,
            local_port: config.local_port,
            public_url,
            created_at: chrono::Utc::now(),
        };
        self.tunnels.push(info.clone());
        Ok(info)
    }

    /// Stop a tunnel by ID.
    pub fn stop(&mut self, tunnel_id: &str) -> anyhow::Result<()> {
        if let Some(t) = self.tunnels.iter_mut().find(|t| t.id == tunnel_id) {
            t.status = TunnelStatus::Stopped;
            Ok(())
        } else {
            anyhow::bail!("Tunnel not found: {tunnel_id}")
        }
    }

    /// Get status of a tunnel by ID.
    pub fn get(&self, tunnel_id: &str) -> Option<&TunnelInfo> {
        self.tunnels.iter().find(|t| t.id == tunnel_id)
    }

    /// List all tunnels.
    pub fn list(&self) -> &[TunnelInfo] {
        &self.tunnels
    }

    /// List only active (Running) tunnels.
    pub fn active(&self) -> Vec<&TunnelInfo> {
        self.tunnels
            .iter()
            .filter(|t| t.status == TunnelStatus::Running)
            .collect()
    }

    /// Remove stopped tunnels from the list.
    pub fn cleanup(&mut self) -> usize {
        let before = self.tunnels.len();
        self.tunnels.retain(|t| t.status != TunnelStatus::Stopped);
        before - self.tunnels.len()
    }

    /// Check if a specific tunnel provider binary is available on the system.
    pub fn is_provider_available(provider: TunnelProvider) -> bool {
        let binary = match provider {
            TunnelProvider::Cloudflared => "cloudflared",
            TunnelProvider::Tailscale => "tailscale",
            TunnelProvider::Ngrok => "ngrok",
            TunnelProvider::Custom => return true,
        };
        // Check if binary exists on PATH (cross-platform)
        std::process::Command::new(binary)
            .arg("--version")
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .is_ok()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cf_config(subdomain: Option<&str>) -> TunnelConfig {
        TunnelConfig {
            provider: TunnelProvider::Cloudflared,
            local_port: 8080,
            subdomain: subdomain.map(|s| s.to_string()),
            auth_token: None,
            extra_args: vec![],
        }
    }

    #[test]
    fn manager_new_is_empty() {
        let mgr = TunnelManager::new();
        assert!(mgr.list().is_empty());
        assert!(mgr.active().is_empty());
    }

    #[test]
    fn create_adds_running_tunnel() {
        let mut mgr = TunnelManager::new();
        let info = mgr.create(&cf_config(Some("test"))).unwrap();
        assert_eq!(info.status, TunnelStatus::Running);
        assert_eq!(info.local_port, 8080);
        assert_eq!(mgr.list().len(), 1);
    }

    #[test]
    fn create_generates_public_url_cloudflared() {
        let mut mgr = TunnelManager::new();
        let info = mgr.create(&cf_config(Some("mysite"))).unwrap();
        assert_eq!(
            info.public_url.as_deref(),
            Some("https://mysite.trycloudflare.com")
        );
    }

    #[test]
    fn create_generates_public_url_tailscale() {
        let mut mgr = TunnelManager::new();
        let config = TunnelConfig {
            provider: TunnelProvider::Tailscale,
            local_port: 3000,
            subdomain: Some("mybox".to_string()),
            auth_token: None,
            extra_args: vec![],
        };
        let info = mgr.create(&config).unwrap();
        assert_eq!(info.public_url.as_deref(), Some("https://mybox.ts.net"));
    }

    #[test]
    fn create_generates_public_url_ngrok() {
        let mut mgr = TunnelManager::new();
        let config = TunnelConfig {
            provider: TunnelProvider::Ngrok,
            local_port: 4000,
            subdomain: Some("demo".to_string()),
            auth_token: None,
            extra_args: vec![],
        };
        let info = mgr.create(&config).unwrap();
        assert_eq!(info.public_url.as_deref(), Some("https://demo.ngrok.io"));
    }

    #[test]
    fn create_without_subdomain_has_no_public_url() {
        let mut mgr = TunnelManager::new();
        let info = mgr.create(&cf_config(None)).unwrap();
        assert!(info.public_url.is_none());
    }

    #[test]
    fn stop_changes_status_to_stopped() {
        let mut mgr = TunnelManager::new();
        let info = mgr.create(&cf_config(Some("test"))).unwrap();
        mgr.stop(&info.id).unwrap();
        let t = mgr.get(&info.id).unwrap();
        assert_eq!(t.status, TunnelStatus::Stopped);
    }

    #[test]
    fn stop_unknown_tunnel_returns_error() {
        let mut mgr = TunnelManager::new();
        assert!(mgr.stop("nonexistent").is_err());
    }

    #[test]
    fn get_returns_matching_tunnel() {
        let mut mgr = TunnelManager::new();
        let info = mgr.create(&cf_config(Some("test"))).unwrap();
        let found = mgr.get(&info.id).unwrap();
        assert_eq!(found.id, info.id);
    }

    #[test]
    fn get_returns_none_for_missing() {
        let mgr = TunnelManager::new();
        assert!(mgr.get("missing-id").is_none());
    }

    #[test]
    fn list_returns_all_tunnels() {
        let mut mgr = TunnelManager::new();
        mgr.create(&cf_config(Some("a"))).unwrap();
        mgr.create(&cf_config(Some("b"))).unwrap();
        assert_eq!(mgr.list().len(), 2);
    }

    #[test]
    fn active_returns_only_running() {
        let mut mgr = TunnelManager::new();
        let t1 = mgr.create(&cf_config(Some("a"))).unwrap();
        mgr.create(&cf_config(Some("b"))).unwrap();
        mgr.stop(&t1.id).unwrap();
        let active = mgr.active();
        assert_eq!(active.len(), 1);
        assert_eq!(active[0].status, TunnelStatus::Running);
    }

    #[test]
    fn cleanup_removes_stopped_tunnels() {
        let mut mgr = TunnelManager::new();
        let t1 = mgr.create(&cf_config(Some("a"))).unwrap();
        mgr.create(&cf_config(Some("b"))).unwrap();
        mgr.stop(&t1.id).unwrap();
        let removed = mgr.cleanup();
        assert_eq!(removed, 1);
        assert_eq!(mgr.list().len(), 1);
    }

    #[test]
    fn tunnel_config_serialization() {
        let config = cf_config(Some("test"));
        let json = serde_json::to_string(&config).unwrap();
        let deserialized: TunnelConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.provider, TunnelProvider::Cloudflared);
        assert_eq!(deserialized.local_port, 8080);
        assert_eq!(deserialized.subdomain.as_deref(), Some("test"));
    }

    #[test]
    fn tunnel_provider_serialization() {
        let provider = TunnelProvider::Tailscale;
        let json = serde_json::to_string(&provider).unwrap();
        let deserialized: TunnelProvider = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized, TunnelProvider::Tailscale);
    }

    #[test]
    fn tunnel_status_serialization() {
        for status in [
            TunnelStatus::Stopped,
            TunnelStatus::Starting,
            TunnelStatus::Running,
            TunnelStatus::Error,
        ] {
            let json = serde_json::to_string(&status).unwrap();
            let deserialized: TunnelStatus = serde_json::from_str(&json).unwrap();
            assert_eq!(deserialized, status);
        }
    }

    #[test]
    fn custom_provider_always_available() {
        assert!(TunnelManager::is_provider_available(TunnelProvider::Custom));
    }
}

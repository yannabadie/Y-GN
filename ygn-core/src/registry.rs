//! Node registry and discovery system for multi-node IoA.
//!
//! Provides the [`NodeRegistry`] trait for registering, discovering, and
//! managing nodes in the Yggdrasil-Grid Nexus distributed runtime, along
//! with an [`InMemoryRegistry`] implementation backed by a `Mutex<HashMap>`.

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Mutex;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Role a node plays in the Y-GN grid.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum NodeRole {
    Brain,
    Core,
    Edge,
    BrainProxy,
}

impl std::fmt::Display for NodeRole {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            NodeRole::Brain => write!(f, "brain"),
            NodeRole::Core => write!(f, "core"),
            NodeRole::Edge => write!(f, "edge"),
            NodeRole::BrainProxy => write!(f, "brain_proxy"),
        }
    }
}

/// Trust level assigned to a node.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TrustTier {
    Trusted,
    Untrusted,
}

impl std::fmt::Display for TrustTier {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TrustTier::Trusted => write!(f, "trusted"),
            TrustTier::Untrusted => write!(f, "untrusted"),
        }
    }
}

/// A network endpoint for reaching a node.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Endpoint {
    /// Protocol identifier: "mcp", "http", or "uacp".
    pub protocol: String,
    /// Network address (e.g. "127.0.0.1:3000").
    pub address: String,
}

/// Metadata describing a node in the grid.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeInfo {
    /// Unique identifier for this node (UUID).
    pub node_id: String,
    /// Role this node plays.
    pub role: NodeRole,
    /// Network endpoints where this node can be reached.
    pub endpoints: Vec<Endpoint>,
    /// Trust level of this node.
    pub trust_tier: TrustTier,
    /// Tool names this node can execute.
    pub capabilities: Vec<String>,
    /// Last time this node was seen (heartbeat timestamp).
    pub last_seen: DateTime<Utc>,
    /// Arbitrary metadata attached to the node.
    pub metadata: serde_json::Value,
}

/// Filter criteria for node discovery.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct DiscoveryFilter {
    /// Filter by node role.
    pub role: Option<NodeRole>,
    /// Filter by trust tier.
    pub trust_tier: Option<TrustTier>,
    /// Filter by capability (tool name the node must support).
    pub capability: Option<String>,
    /// Maximum staleness in seconds — nodes whose `last_seen` is older than
    /// `now - max_staleness_seconds` are excluded.
    pub max_staleness_seconds: Option<u64>,
}

// ---------------------------------------------------------------------------
// Trait
// ---------------------------------------------------------------------------

/// Registry for managing nodes in the Y-GN grid.
#[async_trait]
pub trait NodeRegistry: Send + Sync {
    /// Register a new node (or update an existing one).
    async fn register(&self, node: NodeInfo) -> anyhow::Result<()>;

    /// Remove a node from the registry. Returns `true` if the node was found
    /// and removed, `false` if it was not present.
    async fn deregister(&self, node_id: &str) -> anyhow::Result<bool>;

    /// Discover nodes matching the given filter criteria.
    async fn discover(&self, filter: DiscoveryFilter) -> anyhow::Result<Vec<NodeInfo>>;

    /// Update the `last_seen` timestamp for the given node to `Utc::now()`.
    async fn heartbeat(&self, node_id: &str) -> anyhow::Result<()>;

    /// Look up a single node by ID.
    async fn get(&self, node_id: &str) -> anyhow::Result<Option<NodeInfo>>;
}

// ---------------------------------------------------------------------------
// InMemoryRegistry
// ---------------------------------------------------------------------------

/// A simple in-process node registry backed by a `Mutex<HashMap>`.
#[derive(Debug, Default)]
pub struct InMemoryRegistry {
    nodes: Mutex<HashMap<String, NodeInfo>>,
}

impl InMemoryRegistry {
    /// Create an empty registry.
    pub fn new() -> Self {
        Self::default()
    }
}

#[async_trait]
impl NodeRegistry for InMemoryRegistry {
    async fn register(&self, node: NodeInfo) -> anyhow::Result<()> {
        let mut map = self.nodes.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        map.insert(node.node_id.clone(), node);
        Ok(())
    }

    async fn deregister(&self, node_id: &str) -> anyhow::Result<bool> {
        let mut map = self.nodes.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        Ok(map.remove(node_id).is_some())
    }

    async fn discover(&self, filter: DiscoveryFilter) -> anyhow::Result<Vec<NodeInfo>> {
        let map = self.nodes.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        let now = Utc::now();

        let results = map
            .values()
            .filter(|node| {
                // Role filter
                if let Some(ref role) = filter.role {
                    if &node.role != role {
                        return false;
                    }
                }
                // Trust tier filter
                if let Some(ref tier) = filter.trust_tier {
                    if &node.trust_tier != tier {
                        return false;
                    }
                }
                // Capability filter
                if let Some(ref cap) = filter.capability {
                    if !node.capabilities.iter().any(|c| c == cap) {
                        return false;
                    }
                }
                // Staleness filter
                if let Some(max_secs) = filter.max_staleness_seconds {
                    let age = now
                        .signed_duration_since(node.last_seen)
                        .num_seconds()
                        .max(0) as u64;
                    if age > max_secs {
                        return false;
                    }
                }
                true
            })
            .cloned()
            .collect();

        Ok(results)
    }

    async fn heartbeat(&self, node_id: &str) -> anyhow::Result<()> {
        let mut map = self.nodes.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        match map.get_mut(node_id) {
            Some(node) => {
                node.last_seen = Utc::now();
                Ok(())
            }
            None => Err(anyhow::anyhow!("Node not found: {node_id}")),
        }
    }

    async fn get(&self, node_id: &str) -> anyhow::Result<Option<NodeInfo>> {
        let map = self.nodes.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        Ok(map.get(node_id).cloned())
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;

    /// Helper: create a NodeInfo with sensible defaults.
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
            metadata: serde_json::json!({}),
        }
    }

    #[tokio::test]
    async fn register_and_get() {
        let reg = InMemoryRegistry::new();
        let node = make_node("n1", NodeRole::Edge, TrustTier::Trusted, vec!["echo"]);
        reg.register(node.clone()).await.unwrap();

        let found = reg.get("n1").await.unwrap();
        assert!(found.is_some());
        let found = found.unwrap();
        assert_eq!(found.node_id, "n1");
        assert_eq!(found.role, NodeRole::Edge);
        assert_eq!(found.trust_tier, TrustTier::Trusted);
        assert_eq!(found.capabilities, vec!["echo"]);
    }

    #[tokio::test]
    async fn deregister_removes_node() {
        let reg = InMemoryRegistry::new();
        let node = make_node("n1", NodeRole::Edge, TrustTier::Trusted, vec![]);
        reg.register(node).await.unwrap();

        let removed = reg.deregister("n1").await.unwrap();
        assert!(removed);

        let found = reg.get("n1").await.unwrap();
        assert!(found.is_none());

        // Deregistering again returns false.
        let removed_again = reg.deregister("n1").await.unwrap();
        assert!(!removed_again);
    }

    #[tokio::test]
    async fn heartbeat_updates_last_seen() {
        let reg = InMemoryRegistry::new();
        let mut node = make_node("n1", NodeRole::Core, TrustTier::Trusted, vec![]);
        // Set last_seen to the past.
        node.last_seen = Utc::now() - Duration::seconds(120);
        let old_ts = node.last_seen;
        reg.register(node).await.unwrap();

        reg.heartbeat("n1").await.unwrap();

        let updated = reg.get("n1").await.unwrap().unwrap();
        assert!(updated.last_seen > old_ts);
    }

    #[tokio::test]
    async fn heartbeat_missing_node_errors() {
        let reg = InMemoryRegistry::new();
        let result = reg.heartbeat("nonexistent").await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn discover_by_role() {
        let reg = InMemoryRegistry::new();
        reg.register(make_node("n1", NodeRole::Edge, TrustTier::Trusted, vec![]))
            .await
            .unwrap();
        reg.register(make_node("n2", NodeRole::Core, TrustTier::Trusted, vec![]))
            .await
            .unwrap();
        reg.register(make_node("n3", NodeRole::Edge, TrustTier::Trusted, vec![]))
            .await
            .unwrap();

        let filter = DiscoveryFilter {
            role: Some(NodeRole::Edge),
            ..Default::default()
        };
        let results = reg.discover(filter).await.unwrap();
        assert_eq!(results.len(), 2);
        assert!(results.iter().all(|n| n.role == NodeRole::Edge));
    }

    #[tokio::test]
    async fn discover_by_trust_tier() {
        let reg = InMemoryRegistry::new();
        reg.register(make_node("n1", NodeRole::Edge, TrustTier::Trusted, vec![]))
            .await
            .unwrap();
        reg.register(make_node(
            "n2",
            NodeRole::Edge,
            TrustTier::Untrusted,
            vec![],
        ))
        .await
        .unwrap();

        let filter = DiscoveryFilter {
            trust_tier: Some(TrustTier::Untrusted),
            ..Default::default()
        };
        let results = reg.discover(filter).await.unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].node_id, "n2");
    }

    #[tokio::test]
    async fn discover_by_capability() {
        let reg = InMemoryRegistry::new();
        reg.register(make_node(
            "n1",
            NodeRole::Edge,
            TrustTier::Trusted,
            vec!["echo", "hardware"],
        ))
        .await
        .unwrap();
        reg.register(make_node(
            "n2",
            NodeRole::Edge,
            TrustTier::Trusted,
            vec!["echo"],
        ))
        .await
        .unwrap();

        let filter = DiscoveryFilter {
            capability: Some("hardware".to_string()),
            ..Default::default()
        };
        let results = reg.discover(filter).await.unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].node_id, "n1");
    }

    #[tokio::test]
    async fn staleness_filter() {
        let reg = InMemoryRegistry::new();

        let mut fresh = make_node("fresh", NodeRole::Edge, TrustTier::Trusted, vec![]);
        fresh.last_seen = Utc::now();

        let mut stale = make_node("stale", NodeRole::Edge, TrustTier::Trusted, vec![]);
        stale.last_seen = Utc::now() - Duration::seconds(300);

        reg.register(fresh).await.unwrap();
        reg.register(stale).await.unwrap();

        let filter = DiscoveryFilter {
            max_staleness_seconds: Some(60),
            ..Default::default()
        };
        let results = reg.discover(filter).await.unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].node_id, "fresh");
    }

    #[tokio::test]
    async fn discover_with_combined_filters() {
        let reg = InMemoryRegistry::new();
        reg.register(make_node(
            "n1",
            NodeRole::Core,
            TrustTier::Trusted,
            vec!["echo"],
        ))
        .await
        .unwrap();
        reg.register(make_node(
            "n2",
            NodeRole::Edge,
            TrustTier::Trusted,
            vec!["echo"],
        ))
        .await
        .unwrap();
        reg.register(make_node(
            "n3",
            NodeRole::Core,
            TrustTier::Untrusted,
            vec!["echo"],
        ))
        .await
        .unwrap();
        reg.register(make_node(
            "n4",
            NodeRole::Core,
            TrustTier::Trusted,
            vec!["hardware"],
        ))
        .await
        .unwrap();

        // Only Core + Trusted + echo capability
        let filter = DiscoveryFilter {
            role: Some(NodeRole::Core),
            trust_tier: Some(TrustTier::Trusted),
            capability: Some("echo".to_string()),
            ..Default::default()
        };
        let results = reg.discover(filter).await.unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].node_id, "n1");
    }

    #[test]
    fn node_info_serialization_round_trip() {
        let node = make_node("n1", NodeRole::Brain, TrustTier::Untrusted, vec!["echo"]);
        let json = serde_json::to_string(&node).unwrap();
        let round: NodeInfo = serde_json::from_str(&json).unwrap();
        assert_eq!(round.node_id, "n1");
        assert_eq!(round.role, NodeRole::Brain);
        assert_eq!(round.trust_tier, TrustTier::Untrusted);
    }

    #[tokio::test]
    async fn discover_empty_filter_returns_all() {
        let reg = InMemoryRegistry::new();
        reg.register(make_node("n1", NodeRole::Edge, TrustTier::Trusted, vec![]))
            .await
            .unwrap();
        reg.register(make_node(
            "n2",
            NodeRole::Core,
            TrustTier::Untrusted,
            vec![],
        ))
        .await
        .unwrap();

        let filter = DiscoveryFilter::default();
        let results = reg.discover(filter).await.unwrap();
        assert_eq!(results.len(), 2);
    }
}

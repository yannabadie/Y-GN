//! SQLite-backed persistent registry for node discovery.
//!
//! Provides a [`SqliteRegistry`] implementation of [`NodeRegistry`] that
//! persists node information across restarts using SQLite with WAL mode,
//! following the same pattern as [`crate::sqlite_memory::SqliteMemory`].

use std::sync::Mutex;

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use rusqlite::{params, Connection};

use crate::registry::{DiscoveryFilter, Endpoint, NodeInfo, NodeRegistry, NodeRole, TrustTier};

// ---------------------------------------------------------------------------
// SqliteRegistry
// ---------------------------------------------------------------------------

/// Persistent registry backed by SQLite.
pub struct SqliteRegistry {
    conn: Mutex<Connection>,
}

impl std::fmt::Debug for SqliteRegistry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SqliteRegistry").finish_non_exhaustive()
    }
}

impl SqliteRegistry {
    /// Create a new registry. Pass `":memory:"` for testing.
    pub fn new(path: &str) -> anyhow::Result<Self> {
        let conn = Connection::open(path)?;
        conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS nodes (
                node_id      TEXT PRIMARY KEY,
                role         TEXT NOT NULL,
                trust_tier   TEXT NOT NULL,
                endpoints    TEXT NOT NULL,
                capabilities TEXT NOT NULL,
                last_seen    TEXT NOT NULL,
                metadata     TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_nodes_role ON nodes(role);
            CREATE INDEX IF NOT EXISTS idx_nodes_last_seen ON nodes(last_seen);",
        )?;
        Ok(Self {
            conn: Mutex::new(conn),
        })
    }

    /// Remove nodes whose last_seen is older than max_staleness_seconds.
    /// Returns the number of evicted nodes.
    pub async fn evict_stale(&self, max_staleness_seconds: u64) -> anyhow::Result<usize> {
        let cutoff = Utc::now() - chrono::Duration::seconds(max_staleness_seconds as i64);
        let cutoff_str = cutoff.to_rfc3339();
        let conn = self.conn.lock().unwrap();
        let count = conn.execute(
            "DELETE FROM nodes WHERE last_seen < ?1",
            rusqlite::params![cutoff_str],
        )?;
        Ok(count)
    }
}

// ---------------------------------------------------------------------------
// Serialisation helpers
// ---------------------------------------------------------------------------

fn role_to_str(role: &NodeRole) -> &'static str {
    match role {
        NodeRole::Brain => "brain",
        NodeRole::Core => "core",
        NodeRole::Edge => "edge",
        NodeRole::BrainProxy => "brain_proxy",
    }
}

fn str_to_role(s: &str) -> anyhow::Result<NodeRole> {
    match s {
        "brain" => Ok(NodeRole::Brain),
        "core" => Ok(NodeRole::Core),
        "edge" => Ok(NodeRole::Edge),
        "brain_proxy" => Ok(NodeRole::BrainProxy),
        other => Err(anyhow::anyhow!("unknown node role: {other}")),
    }
}

fn trust_to_str(tier: &TrustTier) -> &'static str {
    match tier {
        TrustTier::Trusted => "trusted",
        TrustTier::Untrusted => "untrusted",
    }
}

fn str_to_trust(s: &str) -> anyhow::Result<TrustTier> {
    match s {
        "trusted" => Ok(TrustTier::Trusted),
        "untrusted" => Ok(TrustTier::Untrusted),
        other => Err(anyhow::anyhow!("unknown trust tier: {other}")),
    }
}

/// Parse a SQLite row into a [`NodeInfo`].
fn row_to_node(row: &rusqlite::Row<'_>) -> rusqlite::Result<NodeInfo> {
    let node_id: String = row.get(0)?;
    let role_str: String = row.get(1)?;
    let trust_str: String = row.get(2)?;
    let endpoints_json: String = row.get(3)?;
    let capabilities_json: String = row.get(4)?;
    let last_seen_str: String = row.get(5)?;
    let metadata_json: String = row.get(6)?;

    let role =
        str_to_role(&role_str).map_err(|_| rusqlite::Error::InvalidColumnName(role_str.clone()))?;
    let trust_tier = str_to_trust(&trust_str)
        .map_err(|_| rusqlite::Error::InvalidColumnName(trust_str.clone()))?;
    let endpoints: Vec<Endpoint> = serde_json::from_str(&endpoints_json).map_err(|e| {
        rusqlite::Error::FromSqlConversionFailure(3, rusqlite::types::Type::Text, Box::new(e))
    })?;
    let capabilities: Vec<String> = serde_json::from_str(&capabilities_json).map_err(|e| {
        rusqlite::Error::FromSqlConversionFailure(4, rusqlite::types::Type::Text, Box::new(e))
    })?;
    let last_seen: DateTime<Utc> = DateTime::parse_from_rfc3339(&last_seen_str)
        .map(|dt| dt.with_timezone(&Utc))
        .unwrap_or_else(|_| Utc::now());
    let metadata: serde_json::Value =
        serde_json::from_str(&metadata_json).unwrap_or_else(|_| serde_json::json!({}));

    Ok(NodeInfo {
        node_id,
        role,
        endpoints,
        trust_tier,
        capabilities,
        last_seen,
        metadata,
    })
}

// ---------------------------------------------------------------------------
// NodeRegistry implementation
// ---------------------------------------------------------------------------

#[async_trait]
impl NodeRegistry for SqliteRegistry {
    async fn register(&self, node: NodeInfo) -> anyhow::Result<()> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        let role = role_to_str(&node.role);
        let trust = trust_to_str(&node.trust_tier);
        let endpoints = serde_json::to_string(&node.endpoints)?;
        let capabilities = serde_json::to_string(&node.capabilities)?;
        let last_seen = node.last_seen.to_rfc3339();
        let metadata = serde_json::to_string(&node.metadata)?;

        conn.execute(
            "INSERT OR REPLACE INTO nodes (node_id, role, trust_tier, endpoints, capabilities, last_seen, metadata)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                &node.node_id,
                role,
                trust,
                &endpoints,
                &capabilities,
                &last_seen,
                &metadata,
            ],
        )?;
        Ok(())
    }

    async fn deregister(&self, node_id: &str) -> anyhow::Result<bool> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        let affected = conn.execute("DELETE FROM nodes WHERE node_id = ?1", params![node_id])?;
        Ok(affected > 0)
    }

    async fn discover(&self, filter: DiscoveryFilter) -> anyhow::Result<Vec<NodeInfo>> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;

        // Build dynamic WHERE clause
        let mut clauses: Vec<String> = Vec::new();
        let mut param_values: Vec<String> = Vec::new();

        if let Some(ref role) = filter.role {
            clauses.push(format!("role = ?{}", param_values.len() + 1));
            param_values.push(role_to_str(role).to_string());
        }
        if let Some(ref tier) = filter.trust_tier {
            clauses.push(format!("trust_tier = ?{}", param_values.len() + 1));
            param_values.push(trust_to_str(tier).to_string());
        }
        if let Some(ref cap) = filter.capability {
            // JSON array contains check via LIKE — e.g. capabilities LIKE '%"echo"%'
            clauses.push(format!("capabilities LIKE ?{}", param_values.len() + 1));
            param_values.push(format!("%\"{cap}\"%"));
        }
        if let Some(max_secs) = filter.max_staleness_seconds {
            let cutoff = Utc::now() - chrono::Duration::seconds(max_secs as i64);
            clauses.push(format!("last_seen >= ?{}", param_values.len() + 1));
            param_values.push(cutoff.to_rfc3339());
        }

        let where_clause = if clauses.is_empty() {
            String::new()
        } else {
            format!(" WHERE {}", clauses.join(" AND "))
        };

        let sql = format!(
            "SELECT node_id, role, trust_tier, endpoints, capabilities, last_seen, metadata FROM nodes{where_clause}"
        );

        let mut stmt = conn.prepare(&sql)?;

        // Build params dynamically — rusqlite needs &dyn ToSql references
        let param_refs: Vec<&dyn rusqlite::types::ToSql> = param_values
            .iter()
            .map(|v| v as &dyn rusqlite::types::ToSql)
            .collect();

        let rows = stmt.query_map(param_refs.as_slice(), row_to_node)?;

        let mut results = Vec::new();
        for row in rows {
            results.push(row?);
        }
        Ok(results)
    }

    async fn heartbeat(&self, node_id: &str) -> anyhow::Result<()> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        let now = Utc::now().to_rfc3339();
        let affected = conn.execute(
            "UPDATE nodes SET last_seen = ?1 WHERE node_id = ?2",
            params![&now, node_id],
        )?;
        if affected == 0 {
            return Err(anyhow::anyhow!("Node not found: {node_id}"));
        }
        Ok(())
    }

    async fn get(&self, node_id: &str) -> anyhow::Result<Option<NodeInfo>> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        let result = conn
            .query_row(
                "SELECT node_id, role, trust_tier, endpoints, capabilities, last_seen, metadata FROM nodes WHERE node_id = ?1",
                params![node_id],
                row_to_node,
            )
            .ok();
        Ok(result)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_node(id: &str) -> NodeInfo {
        NodeInfo {
            node_id: id.to_string(),
            role: NodeRole::Core,
            endpoints: vec![Endpoint {
                protocol: "http".into(),
                address: "127.0.0.1:3000".into(),
            }],
            trust_tier: TrustTier::Trusted,
            capabilities: vec!["echo".into()],
            last_seen: Utc::now(),
            metadata: serde_json::json!({}),
        }
    }

    #[tokio::test]
    async fn register_and_get() {
        let reg = SqliteRegistry::new(":memory:").unwrap();
        reg.register(sample_node("node-1")).await.unwrap();
        let found = reg.get("node-1").await.unwrap();
        assert!(found.is_some());
        assert_eq!(found.unwrap().node_id, "node-1");
    }

    #[tokio::test]
    async fn deregister_removes_node() {
        let reg = SqliteRegistry::new(":memory:").unwrap();
        reg.register(sample_node("node-1")).await.unwrap();
        let removed = reg.deregister("node-1").await.unwrap();
        assert!(removed);
        assert!(reg.get("node-1").await.unwrap().is_none());
    }

    #[tokio::test]
    async fn discover_by_role() {
        let reg = SqliteRegistry::new(":memory:").unwrap();
        let mut brain = sample_node("brain-1");
        brain.role = NodeRole::Brain;
        reg.register(brain).await.unwrap();
        reg.register(sample_node("core-1")).await.unwrap();

        let filter = DiscoveryFilter {
            role: Some(NodeRole::Brain),
            trust_tier: None,
            capability: None,
            max_staleness_seconds: None,
        };
        let results = reg.discover(filter).await.unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].node_id, "brain-1");
    }

    #[tokio::test]
    async fn heartbeat_updates_last_seen() {
        let reg = SqliteRegistry::new(":memory:").unwrap();
        reg.register(sample_node("node-1")).await.unwrap();
        let before = reg.get("node-1").await.unwrap().unwrap().last_seen;

        tokio::time::sleep(std::time::Duration::from_millis(50)).await;
        reg.heartbeat("node-1").await.unwrap();

        let after = reg.get("node-1").await.unwrap().unwrap().last_seen;
        assert!(after > before);
    }

    #[tokio::test]
    async fn deregister_missing_returns_false() {
        let reg = SqliteRegistry::new(":memory:").unwrap();
        let removed = reg.deregister("nonexistent").await.unwrap();
        assert!(!removed);
    }

    #[tokio::test]
    async fn heartbeat_missing_node_errors() {
        let reg = SqliteRegistry::new(":memory:").unwrap();
        let result = reg.heartbeat("nonexistent").await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn discover_by_capability() {
        let reg = SqliteRegistry::new(":memory:").unwrap();
        let mut node = sample_node("multi-1");
        node.capabilities = vec!["echo".into(), "hardware".into()];
        reg.register(node).await.unwrap();
        reg.register(sample_node("echo-only")).await.unwrap();

        let filter = DiscoveryFilter {
            capability: Some("hardware".to_string()),
            ..Default::default()
        };
        let results = reg.discover(filter).await.unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].node_id, "multi-1");
    }

    #[tokio::test]
    async fn discover_empty_filter_returns_all() {
        let reg = SqliteRegistry::new(":memory:").unwrap();
        reg.register(sample_node("a")).await.unwrap();
        reg.register(sample_node("b")).await.unwrap();

        let filter = DiscoveryFilter::default();
        let results = reg.discover(filter).await.unwrap();
        assert_eq!(results.len(), 2);
    }

    #[tokio::test]
    async fn register_upsert_overwrites() {
        let reg = SqliteRegistry::new(":memory:").unwrap();
        let mut node = sample_node("node-1");
        node.capabilities = vec!["old".into()];
        reg.register(node).await.unwrap();

        let mut updated = sample_node("node-1");
        updated.capabilities = vec!["new".into()];
        reg.register(updated).await.unwrap();

        let found = reg.get("node-1").await.unwrap().unwrap();
        assert_eq!(found.capabilities, vec!["new".to_string()]);
    }

    #[tokio::test]
    async fn evict_stale_nodes() {
        let reg = SqliteRegistry::new(":memory:").unwrap();

        // Create a stale node (last_seen 10 minutes ago)
        let mut stale = sample_node("stale-1");
        stale.last_seen = Utc::now() - chrono::Duration::seconds(600);
        reg.register(stale).await.unwrap();

        // Create a fresh node
        reg.register(sample_node("fresh-1")).await.unwrap();

        // Evict nodes older than 5 minutes
        let evicted = reg.evict_stale(300).await.unwrap();
        assert_eq!(evicted, 1);

        assert!(reg.get("stale-1").await.unwrap().is_none());
        assert!(reg.get("fresh-1").await.unwrap().is_some());
    }
}

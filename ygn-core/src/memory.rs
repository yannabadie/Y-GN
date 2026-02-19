//! Memory trait and types.
//!
//! Defines the interface for memory backends (SQLite, Redis, etc.)
//! based on ZeroClaw's Memory trait architecture.

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Category of a memory entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum MemoryCategory {
    /// Core facts that persist indefinitely.
    Core,
    /// Daily summaries and context.
    Daily,
    /// Conversation-scoped memory.
    Conversation,
    /// User-defined category.
    Custom(String),
}

/// A single memory entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEntry {
    pub id: String,
    pub category: MemoryCategory,
    pub key: String,
    pub content: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub metadata: serde_json::Value,
}

// ---------------------------------------------------------------------------
// Trait
// ---------------------------------------------------------------------------

/// Core trait every memory backend must implement.
#[async_trait]
pub trait Memory: Send + Sync {
    /// Store a memory entry (insert or update by key).
    async fn store(
        &self,
        category: MemoryCategory,
        key: &str,
        content: &str,
    ) -> anyhow::Result<MemoryEntry>;

    /// Search memory by query string and optional category filter.
    async fn recall(
        &self,
        query: &str,
        category: Option<MemoryCategory>,
        limit: usize,
    ) -> anyhow::Result<Vec<MemoryEntry>>;

    /// Get a specific memory entry by key.
    async fn get(&self, category: MemoryCategory, key: &str)
        -> anyhow::Result<Option<MemoryEntry>>;

    /// Delete a memory entry by key.
    async fn forget(&self, category: MemoryCategory, key: &str) -> anyhow::Result<bool>;

    /// Check whether the memory backend is healthy.
    async fn health_check(&self) -> anyhow::Result<bool>;
}

// ---------------------------------------------------------------------------
// NoopMemory implementation
// ---------------------------------------------------------------------------

/// A memory backend that does nothing. Useful for testing and as a fallback.
#[derive(Debug, Clone, Default)]
pub struct NoopMemory;

#[async_trait]
impl Memory for NoopMemory {
    async fn store(
        &self,
        category: MemoryCategory,
        key: &str,
        content: &str,
    ) -> anyhow::Result<MemoryEntry> {
        let now = Utc::now();
        Ok(MemoryEntry {
            id: uuid::Uuid::new_v4().to_string(),
            category,
            key: key.to_string(),
            content: content.to_string(),
            created_at: now,
            updated_at: now,
            metadata: serde_json::json!({}),
        })
    }

    async fn recall(
        &self,
        _query: &str,
        _category: Option<MemoryCategory>,
        _limit: usize,
    ) -> anyhow::Result<Vec<MemoryEntry>> {
        Ok(vec![])
    }

    async fn get(
        &self,
        _category: MemoryCategory,
        _key: &str,
    ) -> anyhow::Result<Option<MemoryEntry>> {
        Ok(None)
    }

    async fn forget(&self, _category: MemoryCategory, _key: &str) -> anyhow::Result<bool> {
        Ok(false)
    }

    async fn health_check(&self) -> anyhow::Result<bool> {
        Ok(true)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn noop_memory_store_returns_entry() {
        let mem = NoopMemory;
        let entry = mem
            .store(MemoryCategory::Core, "test-key", "test-content")
            .await
            .unwrap();
        assert_eq!(entry.key, "test-key");
        assert_eq!(entry.content, "test-content");
        assert_eq!(entry.category, MemoryCategory::Core);
        assert!(!entry.id.is_empty());
    }

    #[tokio::test]
    async fn noop_memory_recall_returns_empty() {
        let mem = NoopMemory;
        let results = mem.recall("anything", None, 10).await.unwrap();
        assert!(results.is_empty());
    }

    #[tokio::test]
    async fn noop_memory_get_returns_none() {
        let mem = NoopMemory;
        let result = mem.get(MemoryCategory::Daily, "key").await.unwrap();
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn noop_memory_forget_returns_false() {
        let mem = NoopMemory;
        let result = mem
            .forget(MemoryCategory::Conversation, "key")
            .await
            .unwrap();
        assert!(!result);
    }

    #[tokio::test]
    async fn noop_memory_health_check() {
        let mem = NoopMemory;
        assert!(mem.health_check().await.unwrap());
    }

    #[test]
    fn memory_category_custom() {
        let cat = MemoryCategory::Custom("project-notes".to_string());
        let json = serde_json::to_string(&cat).unwrap();
        let round: MemoryCategory = serde_json::from_str(&json).unwrap();
        assert_eq!(round, cat);
    }

    #[test]
    fn memory_entry_serialization() {
        let entry = MemoryEntry {
            id: "abc".to_string(),
            category: MemoryCategory::Core,
            key: "k".to_string(),
            content: "v".to_string(),
            created_at: Utc::now(),
            updated_at: Utc::now(),
            metadata: serde_json::json!({}),
        };
        let json = serde_json::to_string(&entry).unwrap();
        let round: MemoryEntry = serde_json::from_str(&json).unwrap();
        assert_eq!(round.id, "abc");
    }
}

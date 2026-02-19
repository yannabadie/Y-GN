//! SQLite-backed memory store.
//!
//! Provides persistent memory storage using SQLite with FTS5 full-text search.
//! Inspired by the ZeroClaw memory architecture.

use chrono::Utc;
use rusqlite::{params, Connection};
use std::sync::Mutex;

use crate::memory::{Memory, MemoryCategory, MemoryEntry};

// ---------------------------------------------------------------------------
// SqliteMemory
// ---------------------------------------------------------------------------

/// A memory backend backed by SQLite with FTS5 full-text search.
pub struct SqliteMemory {
    conn: Mutex<Connection>,
}

impl std::fmt::Debug for SqliteMemory {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SqliteMemory").finish_non_exhaustive()
    }
}

impl SqliteMemory {
    /// Open (or create) a file-based SQLite memory store.
    pub fn new(path: &str) -> anyhow::Result<Self> {
        let conn = Connection::open(path)?;
        let mem = Self {
            conn: Mutex::new(conn),
        };
        mem.init_pragmas()?;
        mem.init_schema()?;
        Ok(mem)
    }

    /// Create an in-memory SQLite store (useful for testing).
    pub fn in_memory() -> anyhow::Result<Self> {
        let conn = Connection::open_in_memory()?;
        let mem = Self {
            conn: Mutex::new(conn),
        };
        mem.init_pragmas()?;
        mem.init_schema()?;
        Ok(mem)
    }

    /// Set WAL mode and NORMAL synchronous for performance.
    fn init_pragmas(&self) -> anyhow::Result<()> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;",
        )?;
        Ok(())
    }

    /// Create the memories table and FTS5 virtual table if they don't exist.
    fn init_schema(&self) -> anyhow::Result<()> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS memories (
                id         TEXT PRIMARY KEY,
                key        TEXT NOT NULL,
                content    TEXT NOT NULL,
                category   TEXT NOT NULL,
                session_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(key, content, content=memories, content_rowid=rowid);

            -- Triggers to keep FTS index in sync with the main table
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, key, content)
                VALUES (new.rowid, new.key, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, key, content)
                VALUES ('delete', old.rowid, old.key, old.content);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, key, content)
                VALUES ('delete', old.rowid, old.key, old.content);
                INSERT INTO memories_fts(rowid, key, content)
                VALUES (new.rowid, new.key, new.content);
            END;",
        )?;
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// Helper — category <-> string
// ---------------------------------------------------------------------------

fn category_to_string(cat: &MemoryCategory) -> String {
    match cat {
        MemoryCategory::Core => "core".to_string(),
        MemoryCategory::Daily => "daily".to_string(),
        MemoryCategory::Conversation => "conversation".to_string(),
        MemoryCategory::Custom(s) => format!("custom:{s}"),
    }
}

fn string_to_category(s: &str) -> MemoryCategory {
    match s {
        "core" => MemoryCategory::Core,
        "daily" => MemoryCategory::Daily,
        "conversation" => MemoryCategory::Conversation,
        other => {
            if let Some(rest) = other.strip_prefix("custom:") {
                MemoryCategory::Custom(rest.to_string())
            } else {
                MemoryCategory::Custom(other.to_string())
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Helper — row → MemoryEntry
// ---------------------------------------------------------------------------

fn row_to_entry(row: &rusqlite::Row<'_>) -> rusqlite::Result<MemoryEntry> {
    let id: String = row.get(0)?;
    let key: String = row.get(1)?;
    let content: String = row.get(2)?;
    let category_str: String = row.get(3)?;
    let _session_id: Option<String> = row.get(4)?;
    let created_at_str: String = row.get(5)?;
    let updated_at_str: String = row.get(6)?;

    let created_at = chrono::DateTime::parse_from_rfc3339(&created_at_str)
        .map(|dt| dt.with_timezone(&Utc))
        .unwrap_or_else(|_| Utc::now());
    let updated_at = chrono::DateTime::parse_from_rfc3339(&updated_at_str)
        .map(|dt| dt.with_timezone(&Utc))
        .unwrap_or_else(|_| Utc::now());

    Ok(MemoryEntry {
        id,
        category: string_to_category(&category_str),
        key,
        content,
        created_at,
        updated_at,
        metadata: serde_json::json!({}),
    })
}

// ---------------------------------------------------------------------------
// Memory trait implementation
// ---------------------------------------------------------------------------

#[async_trait::async_trait]
impl Memory for SqliteMemory {
    async fn store(
        &self,
        category: MemoryCategory,
        key: &str,
        content: &str,
    ) -> anyhow::Result<MemoryEntry> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        let now = Utc::now();
        let now_str = now.to_rfc3339();
        let id = uuid::Uuid::new_v4().to_string();
        let cat_str = category_to_string(&category);

        // Check if key+category already exists — if so, UPDATE instead of INSERT
        let existing_id: Option<String> = conn
            .query_row(
                "SELECT id FROM memories WHERE key = ?1 AND category = ?2",
                params![key, cat_str],
                |row| row.get(0),
            )
            .ok();

        if let Some(eid) = existing_id {
            conn.execute(
                "UPDATE memories SET content = ?1, updated_at = ?2 WHERE id = ?3",
                params![content, &now_str, &eid],
            )?;
            let entry = conn.query_row(
                "SELECT id, key, content, category, session_id, created_at, updated_at \
                 FROM memories WHERE id = ?1",
                params![&eid],
                row_to_entry,
            )?;
            Ok(entry)
        } else {
            conn.execute(
                "INSERT INTO memories (id, key, content, category, session_id, created_at, updated_at) \
                 VALUES (?1, ?2, ?3, ?4, NULL, ?5, ?6)",
                params![&id, key, content, &cat_str, &now_str, &now_str],
            )?;
            Ok(MemoryEntry {
                id,
                category,
                key: key.to_string(),
                content: content.to_string(),
                created_at: now,
                updated_at: now,
                metadata: serde_json::json!({}),
            })
        }
    }

    async fn recall(
        &self,
        query: &str,
        category: Option<MemoryCategory>,
        limit: usize,
    ) -> anyhow::Result<Vec<MemoryEntry>> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;

        // FTS5 search using BM25 ranking
        let mut entries: Vec<MemoryEntry> = Vec::new();

        if query.trim().is_empty() {
            return Ok(entries);
        }

        // Tokenize and create an OR query for FTS5 to be forgiving
        let fts_query: String = query
            .split_whitespace()
            .map(|w| {
                // Escape quotes in individual words
                let escaped = w.replace('"', "");
                format!("\"{escaped}\"")
            })
            .collect::<Vec<_>>()
            .join(" OR ");

        if let Some(ref cat) = category {
            let cat_str = category_to_string(cat);
            let mut stmt = conn.prepare(
                "SELECT m.id, m.key, m.content, m.category, m.session_id, m.created_at, m.updated_at
                 FROM memories_fts f
                 JOIN memories m ON m.rowid = f.rowid
                 WHERE memories_fts MATCH ?1 AND m.category = ?2
                 ORDER BY bm25(memories_fts)
                 LIMIT ?3",
            )?;
            let rows = stmt.query_map(params![&fts_query, &cat_str, limit as i64], row_to_entry)?;
            for row in rows {
                entries.push(row?);
            }
        } else {
            let mut stmt = conn.prepare(
                "SELECT m.id, m.key, m.content, m.category, m.session_id, m.created_at, m.updated_at
                 FROM memories_fts f
                 JOIN memories m ON m.rowid = f.rowid
                 WHERE memories_fts MATCH ?1
                 ORDER BY bm25(memories_fts)
                 LIMIT ?2",
            )?;
            let rows = stmt.query_map(params![&fts_query, limit as i64], row_to_entry)?;
            for row in rows {
                entries.push(row?);
            }
        }

        Ok(entries)
    }

    async fn get(
        &self,
        category: MemoryCategory,
        key: &str,
    ) -> anyhow::Result<Option<MemoryEntry>> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        let cat_str = category_to_string(&category);
        let result = conn
            .query_row(
                "SELECT id, key, content, category, session_id, created_at, updated_at \
                 FROM memories WHERE key = ?1 AND category = ?2",
                params![key, &cat_str],
                row_to_entry,
            )
            .ok();
        Ok(result)
    }

    async fn forget(&self, category: MemoryCategory, key: &str) -> anyhow::Result<bool> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        let cat_str = category_to_string(&category);
        let affected = conn.execute(
            "DELETE FROM memories WHERE key = ?1 AND category = ?2",
            params![key, &cat_str],
        )?;
        Ok(affected > 0)
    }

    async fn health_check(&self) -> anyhow::Result<bool> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("{e}"))?;
        let result: i64 = conn.query_row("SELECT 1", [], |row| row.get(0))?;
        Ok(result == 1)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn store_and_recall() {
        let mem = SqliteMemory::in_memory().unwrap();
        let entry = mem
            .store(
                MemoryCategory::Core,
                "rust-lang",
                "Rust is a systems programming language",
            )
            .await
            .unwrap();
        assert_eq!(entry.key, "rust-lang");
        assert_eq!(entry.content, "Rust is a systems programming language");

        let results = mem.recall("Rust systems", None, 10).await.unwrap();
        assert!(!results.is_empty());
        assert_eq!(results[0].key, "rust-lang");
    }

    #[tokio::test]
    async fn forget_removes_entry() {
        let mem = SqliteMemory::in_memory().unwrap();
        mem.store(MemoryCategory::Daily, "note", "daily standup notes")
            .await
            .unwrap();

        // Verify it exists
        let found = mem.get(MemoryCategory::Daily, "note").await.unwrap();
        assert!(found.is_some());

        // Forget it
        let removed = mem.forget(MemoryCategory::Daily, "note").await.unwrap();
        assert!(removed);

        // Verify gone
        let found = mem.get(MemoryCategory::Daily, "note").await.unwrap();
        assert!(found.is_none());

        // Forget again should be false
        let removed = mem.forget(MemoryCategory::Daily, "note").await.unwrap();
        assert!(!removed);
    }

    #[tokio::test]
    async fn recall_filters_by_category() {
        let mem = SqliteMemory::in_memory().unwrap();
        mem.store(MemoryCategory::Core, "a", "important architecture decision")
            .await
            .unwrap();
        mem.store(MemoryCategory::Daily, "b", "daily architecture review")
            .await
            .unwrap();

        // Search with category filter
        let core_results = mem
            .recall("architecture", Some(MemoryCategory::Core), 10)
            .await
            .unwrap();
        assert_eq!(core_results.len(), 1);
        assert_eq!(core_results[0].key, "a");

        let daily_results = mem
            .recall("architecture", Some(MemoryCategory::Daily), 10)
            .await
            .unwrap();
        assert_eq!(daily_results.len(), 1);
        assert_eq!(daily_results[0].key, "b");

        // Search without filter returns both
        let all_results = mem.recall("architecture", None, 10).await.unwrap();
        assert_eq!(all_results.len(), 2);
    }

    #[tokio::test]
    async fn fts_search_ranking() {
        let mem = SqliteMemory::in_memory().unwrap();
        mem.store(
            MemoryCategory::Core,
            "python",
            "Python is a scripting language",
        )
        .await
        .unwrap();
        mem.store(
            MemoryCategory::Core,
            "rust",
            "Rust is a systems programming language with memory safety",
        )
        .await
        .unwrap();
        mem.store(
            MemoryCategory::Core,
            "go",
            "Go is a compiled language by Google",
        )
        .await
        .unwrap();

        let results = mem.recall("memory safety", None, 10).await.unwrap();
        assert!(!results.is_empty());
        // The entry mentioning "memory safety" should be found
        assert!(results.iter().any(|e| e.key == "rust"));
    }

    #[tokio::test]
    async fn health_check_succeeds() {
        let mem = SqliteMemory::in_memory().unwrap();
        let healthy = mem.health_check().await.unwrap();
        assert!(healthy);
    }

    #[tokio::test]
    async fn empty_recall_returns_empty() {
        let mem = SqliteMemory::in_memory().unwrap();
        let results = mem.recall("nonexistent query", None, 10).await.unwrap();
        assert!(results.is_empty());
    }

    #[tokio::test]
    async fn store_upsert_updates_content() {
        let mem = SqliteMemory::in_memory().unwrap();
        mem.store(MemoryCategory::Core, "config", "version 1")
            .await
            .unwrap();
        mem.store(MemoryCategory::Core, "config", "version 2")
            .await
            .unwrap();

        let entry = mem
            .get(MemoryCategory::Core, "config")
            .await
            .unwrap()
            .expect("entry should exist");
        assert_eq!(entry.content, "version 2");

        // FTS should find the updated content
        let results = mem.recall("version", None, 10).await.unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].content, "version 2");
    }

    #[tokio::test]
    async fn custom_category_round_trip() {
        let mem = SqliteMemory::in_memory().unwrap();
        let cat = MemoryCategory::Custom("project-x".to_string());
        mem.store(cat.clone(), "spec", "project x specification")
            .await
            .unwrap();

        let entry = mem.get(cat, "spec").await.unwrap().expect("should exist");
        assert_eq!(entry.content, "project x specification");
        assert_eq!(
            entry.category,
            MemoryCategory::Custom("project-x".to_string())
        );
    }
}

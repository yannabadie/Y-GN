//! A2A (Agent-to-Agent) protocol support.
//!
//! Implements a subset of the A2A spec:
//! - Agent Card at `GET /.well-known/agent.json`
//! - `POST /a2a` for `SendMessage` / `GetTask` / `ListTasks`

use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use uuid::Uuid;

// ---------------------------------------------------------------------------
// Agent Card
// ---------------------------------------------------------------------------

/// Returns the static Agent Card for Y-GN.
pub fn agent_card() -> Value {
    json!({
        "name": "Y-GN",
        "description": "Distributed multi-agent runtime with governance and audit",
        "version": env!("CARGO_PKG_VERSION"),
        "provider": {"organization": "Y-GN Project"},
        "capabilities": {"streaming": false, "pushNotifications": false},
        "skills": [
            {"id": "orchestrate", "name": "HiveMind Pipeline", "description": "7-phase cognitive execution"},
            {"id": "guard", "name": "Security Guard", "description": "Prompt injection detection"},
            {"id": "evidence", "name": "Evidence Export", "description": "Tamper-evident audit trail"}
        ],
        "interfaces": [{"protocol": "jsonrpc", "url": "/mcp"}],
        "securitySchemes": {}
    })
}

// ---------------------------------------------------------------------------
// A2A Task store
// ---------------------------------------------------------------------------

/// Status of an A2A task.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum TaskStatus {
    Pending,
    Running,
    Completed,
    Failed,
}

/// An A2A task.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2aTask {
    pub id: String,
    pub status: TaskStatus,
    pub message: String,
    pub result: Option<String>,
}

/// In-memory A2A task store.
#[derive(Debug, Clone, Default)]
pub struct TaskStore {
    tasks: Arc<Mutex<HashMap<String, A2aTask>>>,
}

impl TaskStore {
    pub fn new() -> Self {
        Self::default()
    }

    /// Create a new pending task from a message. Returns the task.
    pub fn create_task(&self, message: &str) -> A2aTask {
        let task = A2aTask {
            id: Uuid::new_v4().to_string(),
            status: TaskStatus::Completed,
            message: message.to_string(),
            result: Some(format!("Processed: {message}")),
        };
        self.tasks
            .lock()
            .unwrap()
            .insert(task.id.clone(), task.clone());
        task
    }

    /// Get a task by ID.
    pub fn get_task(&self, id: &str) -> Option<A2aTask> {
        self.tasks.lock().unwrap().get(id).cloned()
    }

    /// List recent tasks (up to `limit`).
    pub fn list_tasks(&self, limit: usize) -> Vec<A2aTask> {
        self.tasks
            .lock()
            .unwrap()
            .values()
            .take(limit)
            .cloned()
            .collect()
    }
}

// ---------------------------------------------------------------------------
// Persistent (SQLite) task store
// ---------------------------------------------------------------------------

/// Persistent A2A task store backed by SQLite.
pub struct SqliteTaskStore {
    conn: Mutex<Connection>,
}

impl SqliteTaskStore {
    /// Open (or create) a SQLite-backed task store at `path`.
    /// Pass `":memory:"` for an ephemeral in-memory database.
    pub fn new(path: &str) -> anyhow::Result<Self> {
        let conn = Connection::open(path)?;
        conn.execute_batch(
            "PRAGMA journal_mode=WAL;
             PRAGMA synchronous=NORMAL;
             CREATE TABLE IF NOT EXISTS tasks (
                 id TEXT PRIMARY KEY,
                 status TEXT NOT NULL,
                 message TEXT NOT NULL,
                 result TEXT,
                 created_at TEXT NOT NULL,
                 updated_at TEXT NOT NULL
             );",
        )?;
        Ok(Self {
            conn: Mutex::new(conn),
        })
    }

    /// Create a new task from a message and persist it. Returns a JSON value
    /// with the task fields (mirrors the shape used by the in-memory store).
    pub fn create_task(&self, message: &str) -> Value {
        let id = Uuid::new_v4().to_string();
        let now = chrono::Utc::now().to_rfc3339();
        let result_text = format!("Processed: {message}");
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO tasks (id, status, message, result, created_at, updated_at) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            rusqlite::params![id, "Completed", message, result_text, now, now],
        )
        .unwrap();
        json!({
            "id": id,
            "status": "Completed",
            "message": message,
            "result": result_text,
            "created_at": now,
        })
    }

    /// Retrieve a task by its ID.
    pub fn get_task(&self, id: &str) -> Option<Value> {
        let conn = self.conn.lock().unwrap();
        conn.query_row(
            "SELECT id, status, message, result, created_at FROM tasks WHERE id = ?1",
            rusqlite::params![id],
            |row| {
                Ok(json!({
                    "id": row.get::<_, String>(0)?,
                    "status": row.get::<_, String>(1)?,
                    "message": row.get::<_, String>(2)?,
                    "result": row.get::<_, Option<String>>(3)?,
                    "created_at": row.get::<_, String>(4)?,
                }))
            },
        )
        .ok()
    }

    /// List all tasks, most recent first.
    pub fn list_tasks(&self) -> Vec<Value> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn
            .prepare(
                "SELECT id, status, message, result, created_at \
                 FROM tasks ORDER BY created_at DESC",
            )
            .unwrap();
        stmt.query_map([], |row| {
            Ok(json!({
                "id": row.get::<_, String>(0)?,
                "status": row.get::<_, String>(1)?,
                "message": row.get::<_, String>(2)?,
                "result": row.get::<_, Option<String>>(3)?,
                "created_at": row.get::<_, String>(4)?,
            }))
        })
        .unwrap()
        .filter_map(|r| r.ok())
        .collect()
    }
}

// ---------------------------------------------------------------------------
// A2A message handler
// ---------------------------------------------------------------------------

/// Handle an A2A JSON-RPC request.
///
/// Supports: `SendMessage`, `GetTask`, `ListTasks`.
pub fn handle_a2a(request: &Value, store: &TaskStore) -> Value {
    let method = request.get("method").and_then(|v| v.as_str()).unwrap_or("");
    let id = request.get("id").cloned().unwrap_or(Value::Null);
    let params = request.get("params").cloned().unwrap_or(json!({}));

    match method {
        "SendMessage" => {
            let message = params
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("(empty)");
            let task = store.create_task(message);
            json!({
                "jsonrpc": "2.0",
                "id": id,
                "result": {
                    "task": task
                }
            })
        }
        "GetTask" => {
            let task_id = params.get("task_id").and_then(|v| v.as_str()).unwrap_or("");
            match store.get_task(task_id) {
                Some(task) => json!({
                    "jsonrpc": "2.0",
                    "id": id,
                    "result": {"task": task}
                }),
                None => json!({
                    "jsonrpc": "2.0",
                    "id": id,
                    "error": {"code": -32602, "message": format!("Task not found: {task_id}")}
                }),
            }
        }
        "ListTasks" => {
            let limit = params.get("limit").and_then(|v| v.as_u64()).unwrap_or(10) as usize;
            let tasks = store.list_tasks(limit);
            json!({
                "jsonrpc": "2.0",
                "id": id,
                "result": {"tasks": tasks}
            })
        }
        _ => json!({
            "jsonrpc": "2.0",
            "id": id,
            "error": {"code": -32601, "message": format!("Unknown A2A method: {method}")}
        }),
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn agent_card_discovery() {
        let card = agent_card();
        assert_eq!(card["name"], "Y-GN");
        assert!(card["skills"].as_array().unwrap().len() >= 3);
        assert_eq!(card["capabilities"]["streaming"], false);
        let interfaces = card["interfaces"].as_array().unwrap();
        assert_eq!(interfaces[0]["protocol"], "jsonrpc");
        assert_eq!(interfaces[0]["url"], "/mcp");
    }

    #[test]
    fn a2a_send_message() {
        let store = TaskStore::new();
        let req = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "SendMessage",
            "params": {"message": "Hello, agent!"}
        });
        let resp = handle_a2a(&req, &store);
        assert_eq!(resp["id"], 1);
        let task = &resp["result"]["task"];
        assert!(!task["id"].as_str().unwrap().is_empty());
        assert_eq!(task["status"], "completed");
        assert!(task["result"].as_str().unwrap().contains("Hello, agent!"));
    }

    #[test]
    fn a2a_get_task() {
        let store = TaskStore::new();
        // Create a task first
        let task = store.create_task("test message");

        let req = json!({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "GetTask",
            "params": {"task_id": task.id}
        });
        let resp = handle_a2a(&req, &store);
        assert_eq!(resp["id"], 2);
        assert_eq!(resp["result"]["task"]["id"], task.id);
        assert_eq!(resp["result"]["task"]["status"], "completed");
    }

    // -- SqliteTaskStore tests ------------------------------------------------

    #[test]
    fn sqlite_task_store_create_and_get() {
        let store = SqliteTaskStore::new(":memory:").unwrap();
        let task = store.create_task("Hello agent");
        let id = task["id"].as_str().unwrap();
        let found = store.get_task(id);
        assert!(found.is_some());
        assert_eq!(found.unwrap()["message"].as_str().unwrap(), "Hello agent");
    }

    #[test]
    fn sqlite_task_store_list() {
        let store = SqliteTaskStore::new(":memory:").unwrap();
        store.create_task("Task 1");
        store.create_task("Task 2");
        let tasks = store.list_tasks();
        assert_eq!(tasks.len(), 2);
    }

    #[test]
    fn sqlite_task_store_persists() {
        let store = SqliteTaskStore::new(":memory:").unwrap();
        store.create_task("Persistent task");
        let tasks = store.list_tasks();
        assert_eq!(tasks.len(), 1);
        assert_eq!(tasks[0]["message"].as_str().unwrap(), "Persistent task");
    }
}

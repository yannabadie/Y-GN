//! Security audit trail.
//!
//! Records security-relevant events (tool-call attempts, access decisions,
//! policy violations) for later inspection and compliance.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// The kind of audit event.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum AuditEventType {
    /// A tool call was attempted.
    ToolCallAttempt,
    /// Access was denied by sandbox or policy.
    AccessDenied,
    /// Access was granted.
    AccessGranted,
    /// Approval was required before execution.
    ApprovalRequired,
    /// A policy violation was detected.
    PolicyViolation,
}

/// A single entry in the audit log.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    /// When the event occurred.
    pub timestamp: DateTime<Utc>,
    /// What kind of event this is.
    pub event_type: AuditEventType,
    /// The name of the tool involved.
    pub tool_name: String,
    /// The decision that was made (e.g. "Allow", "Deny").
    pub decision: String,
    /// Risk level at the time of the decision.
    pub risk_level: String,
    /// Arbitrary JSON details (arguments, reasons, etc.).
    pub details: Value,
}

impl AuditEntry {
    /// Convenience constructor that fills in the current UTC timestamp.
    pub fn now(
        event_type: AuditEventType,
        tool_name: impl Into<String>,
        decision: impl Into<String>,
        risk_level: impl Into<String>,
        details: Value,
    ) -> Self {
        Self {
            timestamp: Utc::now(),
            event_type,
            tool_name: tool_name.into(),
            decision: decision.into(),
            risk_level: risk_level.into(),
            details,
        }
    }
}

// ---------------------------------------------------------------------------
// AuditLog
// ---------------------------------------------------------------------------

/// An append-only, in-memory audit log.
#[derive(Debug, Clone, Default)]
pub struct AuditLog {
    entries: Vec<AuditEntry>,
}

impl AuditLog {
    /// Create an empty audit log.
    pub fn new() -> Self {
        Self::default()
    }

    /// Append an entry to the log.
    pub fn record(&mut self, entry: AuditEntry) {
        self.entries.push(entry);
    }

    /// Return all entries.
    pub fn entries(&self) -> &[AuditEntry] {
        &self.entries
    }

    /// Number of entries recorded so far.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether the log is empty.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Serialize the entire log to JSON Lines (one JSON object per line).
    pub fn to_jsonl(&self) -> String {
        self.entries
            .iter()
            .filter_map(|e| serde_json::to_string(e).ok())
            .collect::<Vec<_>>()
            .join("\n")
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn record_and_retrieve_entries() {
        let mut log = AuditLog::new();
        assert!(log.is_empty());

        log.record(AuditEntry::now(
            AuditEventType::ToolCallAttempt,
            "echo",
            "Allow",
            "Low",
            json!({"input": "hello"}),
        ));
        log.record(AuditEntry::now(
            AuditEventType::AccessDenied,
            "shell_exec",
            "Deny",
            "High",
            json!({"reason": "blocked by policy"}),
        ));

        assert_eq!(log.len(), 2);
        assert!(!log.is_empty());

        let entries = log.entries();
        assert_eq!(entries[0].tool_name, "echo");
        assert_eq!(entries[0].event_type, AuditEventType::ToolCallAttempt);
        assert_eq!(entries[1].tool_name, "shell_exec");
        assert_eq!(entries[1].event_type, AuditEventType::AccessDenied);
    }

    #[test]
    fn to_jsonl_produces_valid_lines() {
        let mut log = AuditLog::new();
        log.record(AuditEntry::now(
            AuditEventType::AccessGranted,
            "read_file",
            "Allow",
            "Low",
            json!({}),
        ));
        log.record(AuditEntry::now(
            AuditEventType::PolicyViolation,
            "nuke",
            "Deny",
            "Critical",
            json!({"violation": "tool on deny list"}),
        ));

        let jsonl = log.to_jsonl();
        let lines: Vec<&str> = jsonl.lines().collect();
        assert_eq!(lines.len(), 2);

        // Each line must be valid JSON.
        for line in &lines {
            let parsed: serde_json::Result<Value> = serde_json::from_str(line);
            assert!(parsed.is_ok(), "Line is not valid JSON: {}", line);
        }
    }

    #[test]
    fn audit_entry_serialization_roundtrip() {
        let entry = AuditEntry::now(
            AuditEventType::ApprovalRequired,
            "deploy",
            "RequireApproval",
            "High",
            json!({"target": "production"}),
        );

        let json_str = serde_json::to_string(&entry).unwrap();
        let round: AuditEntry = serde_json::from_str(&json_str).unwrap();

        assert_eq!(round.tool_name, "deploy");
        assert_eq!(round.event_type, AuditEventType::ApprovalRequired);
        assert_eq!(round.decision, "RequireApproval");
        assert_eq!(round.risk_level, "High");
        assert_eq!(round.details["target"], "production");
    }

    #[test]
    fn empty_log_produces_empty_jsonl() {
        let log = AuditLog::new();
        assert_eq!(log.to_jsonl(), "");
    }
}

//! Unified policy engine for tool execution.
//!
//! Evaluates tool-call requests against security rules, sandbox restrictions,
//! and explicit allow/deny lists.  Produces a [`PolicyDecision`] that the MCP
//! layer uses to gate execution.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::time::Duration;

use crate::sandbox::SandboxChecker;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// The action dictated by the policy engine.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum PolicyAction {
    /// Execution may proceed.
    Allow,
    /// Execution is forbidden.
    Deny,
    /// Execution requires explicit user approval before proceeding.
    RequireApproval,
}

/// Risk classification for a tool call.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum RiskLevel {
    Low,
    Medium,
    High,
    Critical,
}

/// The decision returned by [`PolicyEngine::evaluate`].
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyDecision {
    /// What to do with the tool call.
    pub action: PolicyAction,
    /// Human-readable explanation.
    pub reason: String,
    /// Risk classification for this call.
    pub risk_level: RiskLevel,
}

// ---------------------------------------------------------------------------
// PolicyEngine
// ---------------------------------------------------------------------------

/// Evaluates tool-call requests against a set of security rules.
pub struct PolicyEngine {
    sandbox: Box<dyn SandboxChecker>,
    /// Tool names that require explicit user approval before execution.
    approval_required: Vec<String>,
    /// Tool names that are always blocked.
    denied_tools: Vec<String>,
    /// Maximum wall-clock time a tool is allowed to run.
    #[allow(dead_code)]
    max_execution_time: Duration,
}

impl PolicyEngine {
    /// Create a new policy engine.
    pub fn new(
        sandbox: Box<dyn SandboxChecker>,
        approval_required: Vec<String>,
        denied_tools: Vec<String>,
        max_execution_time: Duration,
    ) -> Self {
        Self {
            sandbox,
            approval_required,
            denied_tools,
            max_execution_time,
        }
    }

    /// Evaluate a tool-call request and produce a [`PolicyDecision`].
    ///
    /// Rules (evaluated in order):
    ///
    /// 1. If the tool is on the **denied** list -> `Deny` / `Critical`.
    /// 2. If the tool is on the **approval-required** list -> `RequireApproval` / `High`.
    /// 3. If the tool name matches known shell/command patterns -> `RequireApproval` / `High`.
    /// 4. If the tool involves file writes -> `Allow` / `Medium`
    ///    (sandbox may still deny if outside allowed paths).
    /// 5. Everything else -> `Allow` / `Low`.
    pub fn evaluate(&self, tool_name: &str, args: &Value) -> PolicyDecision {
        // --- 1. Denied tools --------------------------------------------------
        if self.is_denied(tool_name) {
            return PolicyDecision {
                action: PolicyAction::Deny,
                reason: format!("Tool '{}' is on the deny list", tool_name),
                risk_level: RiskLevel::Critical,
            };
        }

        // --- 2. Explicit approval list ----------------------------------------
        if self.requires_approval(tool_name) {
            return PolicyDecision {
                action: PolicyAction::RequireApproval,
                reason: format!(
                    "Tool '{}' requires explicit approval before execution",
                    tool_name
                ),
                risk_level: RiskLevel::High,
            };
        }

        // --- 3. Shell / command heuristics ------------------------------------
        if Self::is_shell_tool(tool_name) {
            return PolicyDecision {
                action: PolicyAction::RequireApproval,
                reason: format!(
                    "Tool '{}' is a shell/command tool — user approval required",
                    tool_name
                ),
                risk_level: RiskLevel::High,
            };
        }

        // --- 4. File-write heuristics -----------------------------------------
        if Self::is_file_write_tool(tool_name, args) {
            return PolicyDecision {
                action: PolicyAction::Allow,
                reason: format!(
                    "Tool '{}' involves file writes — allowed at Medium risk",
                    tool_name
                ),
                risk_level: RiskLevel::Medium,
            };
        }

        // --- 5. Default: low-risk allow ---------------------------------------
        PolicyDecision {
            action: PolicyAction::Allow,
            reason: format!("Tool '{}' is allowed at Low risk", tool_name),
            risk_level: RiskLevel::Low,
        }
    }

    /// Access the underlying sandbox checker (e.g. for the MCP layer to run
    /// fine-grained access checks on arguments).
    pub fn sandbox(&self) -> &dyn SandboxChecker {
        &*self.sandbox
    }

    /// Maximum execution time configured for tools.
    pub fn max_execution_time(&self) -> Duration {
        self.max_execution_time
    }

    // -- private helpers ---------------------------------------------------

    fn is_denied(&self, tool_name: &str) -> bool {
        self.denied_tools.iter().any(|d| d == tool_name)
    }

    fn requires_approval(&self, tool_name: &str) -> bool {
        self.approval_required.iter().any(|a| a == tool_name)
    }

    /// Heuristic: tool names that look like shell/command execution.
    fn is_shell_tool(tool_name: &str) -> bool {
        let lower = tool_name.to_lowercase();
        let shell_patterns = [
            "shell",
            "bash",
            "exec",
            "command",
            "run",
            "terminal",
            "system",
            "subprocess",
        ];
        shell_patterns.iter().any(|p| lower.contains(p))
    }

    /// Heuristic: tool names or arguments suggesting file writes.
    fn is_file_write_tool(tool_name: &str, args: &Value) -> bool {
        let lower = tool_name.to_lowercase();
        let write_patterns = ["write", "save", "create_file", "edit", "patch", "append"];
        if write_patterns.iter().any(|p| lower.contains(p)) {
            return true;
        }
        // Check for a "path" or "file" argument with a write-ish intent.
        if let Some(obj) = args.as_object() {
            if obj.contains_key("write_path") || obj.contains_key("output_path") {
                return true;
            }
        }
        false
    }
}

impl std::fmt::Debug for PolicyEngine {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("PolicyEngine")
            .field("approval_required", &self.approval_required)
            .field("denied_tools", &self.denied_tools)
            .field("max_execution_time", &self.max_execution_time)
            .finish()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sandbox::{AccessRequest, AccessResult, SandboxChecker};

    /// Stub sandbox that always allows.
    struct AllowAllSandbox;

    impl SandboxChecker for AllowAllSandbox {
        fn check_access(&self, _request: &AccessRequest) -> AccessResult {
            AccessResult {
                allowed: true,
                reason: "stub".into(),
                profile: "test".into(),
            }
        }
        fn profile_name(&self) -> &str {
            "AllowAll"
        }
    }

    fn engine(approval: Vec<&str>, denied: Vec<&str>) -> PolicyEngine {
        PolicyEngine::new(
            Box::new(AllowAllSandbox),
            approval.into_iter().map(String::from).collect(),
            denied.into_iter().map(String::from).collect(),
            Duration::from_secs(30),
        )
    }

    #[test]
    fn denied_tool_returns_deny_critical() {
        let pe = engine(vec![], vec!["dangerous_tool"]);
        let decision = pe.evaluate("dangerous_tool", &serde_json::json!({}));
        assert_eq!(decision.action, PolicyAction::Deny);
        assert_eq!(decision.risk_level, RiskLevel::Critical);
        assert!(decision.reason.contains("deny list"));
    }

    #[test]
    fn approval_required_tool_returns_require_approval() {
        let pe = engine(vec!["deploy"], vec![]);
        let decision = pe.evaluate("deploy", &serde_json::json!({}));
        assert_eq!(decision.action, PolicyAction::RequireApproval);
        assert_eq!(decision.risk_level, RiskLevel::High);
    }

    #[test]
    fn shell_tool_detected_by_name() {
        let pe = engine(vec![], vec![]);
        for name in ["bash_exec", "run_command", "shell", "system_call"] {
            let decision = pe.evaluate(name, &serde_json::json!({}));
            assert_eq!(
                decision.action,
                PolicyAction::RequireApproval,
                "Expected RequireApproval for '{}'",
                name
            );
            assert_eq!(decision.risk_level, RiskLevel::High);
        }
    }

    #[test]
    fn file_write_tool_detected_by_name() {
        let pe = engine(vec![], vec![]);
        let decision = pe.evaluate("write_file", &serde_json::json!({}));
        assert_eq!(decision.action, PolicyAction::Allow);
        assert_eq!(decision.risk_level, RiskLevel::Medium);
    }

    #[test]
    fn file_write_detected_by_args() {
        let pe = engine(vec![], vec![]);
        let args = serde_json::json!({ "output_path": "/tmp/out.txt" });
        let decision = pe.evaluate("some_tool", &args);
        assert_eq!(decision.action, PolicyAction::Allow);
        assert_eq!(decision.risk_level, RiskLevel::Medium);
    }

    #[test]
    fn echo_tool_is_low_risk_allow() {
        let pe = engine(vec![], vec![]);
        let decision = pe.evaluate("echo", &serde_json::json!({"input": "hello"}));
        assert_eq!(decision.action, PolicyAction::Allow);
        assert_eq!(decision.risk_level, RiskLevel::Low);
    }

    #[test]
    fn deny_takes_precedence_over_approval() {
        // If a tool is both denied and on the approval list, deny wins.
        let pe = engine(vec!["nuke"], vec!["nuke"]);
        let decision = pe.evaluate("nuke", &serde_json::json!({}));
        assert_eq!(decision.action, PolicyAction::Deny);
        assert_eq!(decision.risk_level, RiskLevel::Critical);
    }

    #[test]
    fn sandbox_accessor_works() {
        let pe = engine(vec![], vec![]);
        assert_eq!(pe.sandbox().profile_name(), "AllowAll");
    }
}

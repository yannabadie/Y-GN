//! Security policy and sandbox trait.
//!
//! Defines the interface for sandboxing and security policies
//! based on ZeroClaw's security module.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Level of autonomy granted to the agent.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum AutonomyLevel {
    /// Always ask the user before executing.
    Ask,
    /// Execute without asking.
    Allow,
    /// Never execute.
    Deny,
}

/// Security policy that governs what the agent is allowed to do.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityPolicy {
    pub autonomy_level: AutonomyLevel,
    pub allowed_commands: Vec<String>,
    pub allowed_paths: Vec<PathBuf>,
}

impl Default for SecurityPolicy {
    fn default() -> Self {
        Self {
            autonomy_level: AutonomyLevel::Ask,
            allowed_commands: vec![],
            allowed_paths: vec![],
        }
    }
}

impl SecurityPolicy {
    /// Check whether a command is allowed by this policy.
    pub fn is_command_allowed(&self, command: &str) -> bool {
        match self.autonomy_level {
            AutonomyLevel::Deny => false,
            AutonomyLevel::Allow => {
                if self.allowed_commands.is_empty() {
                    true
                } else {
                    self.allowed_commands.iter().any(|c| c == command)
                }
            }
            AutonomyLevel::Ask => self.allowed_commands.iter().any(|c| c == command),
        }
    }

    /// Check whether a path is allowed by this policy.
    pub fn is_path_allowed(&self, path: &std::path::Path) -> bool {
        if self.allowed_paths.is_empty() {
            return true;
        }
        self.allowed_paths.iter().any(|p| path.starts_with(p))
    }
}

// ---------------------------------------------------------------------------
// Sandbox trait
// ---------------------------------------------------------------------------

/// Trait for command sandboxing backends.
#[async_trait]
pub trait Sandbox: Send + Sync {
    /// Human-readable name of this sandbox.
    fn name(&self) -> &str;

    /// Whether this sandbox is available on the current system.
    fn is_available(&self) -> bool;

    /// Wrap a command with sandbox invocation. Returns the modified
    /// command and arguments.
    fn wrap_command(&self, command: &str, args: &[String]) -> (String, Vec<String>);
}

// ---------------------------------------------------------------------------
// NoopSandbox
// ---------------------------------------------------------------------------

/// A sandbox that does not modify commands. Used when no sandboxing is
/// available or needed.
#[derive(Debug, Clone, Default)]
pub struct NoopSandbox;

#[async_trait]
impl Sandbox for NoopSandbox {
    fn name(&self) -> &str {
        "noop"
    }

    fn is_available(&self) -> bool {
        true
    }

    fn wrap_command(&self, command: &str, args: &[String]) -> (String, Vec<String>) {
        (command.to_string(), args.to_vec())
    }
}

// ---------------------------------------------------------------------------
// Credential scrubbing
// ---------------------------------------------------------------------------

/// Scrub credentials and sensitive tokens from output text.
///
/// Redacts patterns that look like API keys, bearer tokens, passwords,
/// and other secrets.
pub fn scrub_credentials(output: &str) -> String {
    use regex::Regex;

    let patterns = [
        // Bearer tokens
        (
            Regex::new(r"(?i)(bearer\s+)[a-zA-Z0-9\-_\.]{10,}").unwrap(),
            "${1}[REDACTED]",
        ),
        // API keys in header-like patterns (key=value or key: value)
        (
            Regex::new(r"(?i)(api[_-]?key\s*[:=]\s*)[a-zA-Z0-9\-_\.]{8,}").unwrap(),
            "${1}[REDACTED]",
        ),
        // Generic tokens (token=... or token: ...)
        (
            Regex::new(r"(?i)(token\s*[:=]\s*)[a-zA-Z0-9\-_\.]{8,}").unwrap(),
            "${1}[REDACTED]",
        ),
        // Password patterns
        (
            Regex::new(r"(?i)(password\s*[:=]\s*)\S+").unwrap(),
            "${1}[REDACTED]",
        ),
        // sk-... style keys (OpenAI, Anthropic)
        (Regex::new(r"sk-[a-zA-Z0-9\-_]{20,}").unwrap(), "[REDACTED]"),
        // xoxb/xoxp Slack tokens
        (
            Regex::new(r"xox[bpras]-[a-zA-Z0-9\-]{10,}").unwrap(),
            "[REDACTED]",
        ),
    ];

    let mut result = output.to_string();
    for (re, replacement) in &patterns {
        result = re.replace_all(&result, *replacement).to_string();
    }
    result
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scrub_bearer_token() {
        let input = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0";
        let scrubbed = scrub_credentials(input);
        assert!(scrubbed.contains("[REDACTED]"));
        assert!(!scrubbed.contains("eyJhbGci"));
    }

    #[test]
    fn scrub_api_key() {
        let input = "api_key: sk-abc123def456ghi789jkl012mno345pqr678";
        let scrubbed = scrub_credentials(input);
        assert!(scrubbed.contains("[REDACTED]"));
        assert!(!scrubbed.contains("abc123def456"));
    }

    #[test]
    fn scrub_password() {
        let input = "password=my_super_secret_password123";
        let scrubbed = scrub_credentials(input);
        assert!(scrubbed.contains("[REDACTED]"));
        assert!(!scrubbed.contains("my_super_secret"));
    }

    #[test]
    fn scrub_sk_key() {
        let input = "Key is sk-proj-abcdef1234567890abcdef1234567890";
        let scrubbed = scrub_credentials(input);
        assert!(scrubbed.contains("[REDACTED]"));
        assert!(!scrubbed.contains("sk-proj-abcdef"));
    }

    #[test]
    fn scrub_slack_token() {
        let input = "SLACK_TOKEN=xoxb-1234567890-abcdefghij";
        let scrubbed = scrub_credentials(input);
        assert!(scrubbed.contains("[REDACTED]"));
        assert!(!scrubbed.contains("xoxb-1234567890"));
    }

    #[test]
    fn scrub_preserves_safe_text() {
        let input = "This is a normal log line with no secrets.";
        let scrubbed = scrub_credentials(input);
        assert_eq!(scrubbed, input);
    }

    #[test]
    fn noop_sandbox_passes_through() {
        let sandbox = NoopSandbox;
        assert_eq!(sandbox.name(), "noop");
        assert!(sandbox.is_available());

        let args = vec!["--flag".to_string(), "value".to_string()];
        let (cmd, wrapped_args) = sandbox.wrap_command("echo", &args);
        assert_eq!(cmd, "echo");
        assert_eq!(wrapped_args, args);
    }

    #[test]
    fn default_security_policy() {
        let policy = SecurityPolicy::default();
        assert_eq!(policy.autonomy_level, AutonomyLevel::Ask);
        assert!(policy.allowed_commands.is_empty());
        assert!(policy.allowed_paths.is_empty());
    }

    #[test]
    fn security_policy_deny_blocks_all() {
        let policy = SecurityPolicy {
            autonomy_level: AutonomyLevel::Deny,
            allowed_commands: vec!["echo".to_string()],
            allowed_paths: vec![],
        };
        assert!(!policy.is_command_allowed("echo"));
        assert!(!policy.is_command_allowed("rm"));
    }

    #[test]
    fn security_policy_allow_with_list() {
        let policy = SecurityPolicy {
            autonomy_level: AutonomyLevel::Allow,
            allowed_commands: vec!["echo".to_string(), "ls".to_string()],
            allowed_paths: vec![],
        };
        assert!(policy.is_command_allowed("echo"));
        assert!(!policy.is_command_allowed("rm"));
    }

    #[test]
    fn security_policy_allow_with_empty_list() {
        let policy = SecurityPolicy {
            autonomy_level: AutonomyLevel::Allow,
            allowed_commands: vec![],
            allowed_paths: vec![],
        };
        // Empty allowed_commands with Allow level permits everything
        assert!(policy.is_command_allowed("anything"));
    }

    #[test]
    fn security_policy_path_check() {
        let policy = SecurityPolicy {
            autonomy_level: AutonomyLevel::Allow,
            allowed_commands: vec![],
            allowed_paths: vec![PathBuf::from("/home/user/project")],
        };
        assert!(policy.is_path_allowed(std::path::Path::new("/home/user/project/src/main.rs")));
        assert!(!policy.is_path_allowed(std::path::Path::new("/etc/passwd")));
    }
}

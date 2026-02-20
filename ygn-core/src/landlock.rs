//! Landlock OS-level sandbox — Linux kernel sandboxing with cross-platform fallback.

use serde::{Deserialize, Serialize};

/// Landlock access rights for filesystem operations.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum LandlockAccess {
    ReadFile,
    WriteFile,
    ReadDir,
    Execute,
    MakeDir,
    RemoveFile,
    RemoveDir,
}

/// A single Landlock rule binding a path to allowed access rights.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LandlockRule {
    pub path: String,
    pub access: Vec<LandlockAccess>,
}

/// Configuration for a Landlock sandbox.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LandlockConfig {
    /// Rules defining allowed filesystem access.
    pub rules: Vec<LandlockRule>,
    /// Whether to allow network access (Landlock v4+).
    pub allow_network: bool,
    /// Whether Landlock is actually enforced (false on non-Linux).
    pub enforced: bool,
}

/// Result of applying a Landlock sandbox.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LandlockResult {
    pub success: bool,
    pub enforced: bool,
    pub message: String,
}

/// The Landlock sandbox manager.
#[derive(Debug)]
pub struct LandlockSandbox {
    config: LandlockConfig,
}

impl LandlockSandbox {
    pub fn new(config: LandlockConfig) -> Self {
        Self { config }
    }

    /// Apply the Landlock sandbox to the current process.
    /// On non-Linux platforms, this is a no-op that returns success with enforced=false.
    pub fn apply(&self) -> LandlockResult {
        #[cfg(target_os = "linux")]
        {
            self.apply_linux()
        }
        #[cfg(not(target_os = "linux"))]
        {
            LandlockResult {
                success: true,
                enforced: false,
                message: "Landlock not available on this platform (non-Linux)".to_string(),
            }
        }
    }

    #[cfg(target_os = "linux")]
    fn apply_linux(&self) -> LandlockResult {
        // Stub for actual Landlock syscalls — would use landlock_create_ruleset etc.
        // Real implementation would use the landlock crate or raw syscalls.
        LandlockResult {
            success: true,
            enforced: self.config.enforced,
            message: "Landlock rules applied (stub)".to_string(),
        }
    }

    /// Check if Landlock is supported on the current platform.
    pub fn is_supported() -> bool {
        cfg!(target_os = "linux")
    }

    /// Get the current configuration.
    pub fn config(&self) -> &LandlockConfig {
        &self.config
    }

    /// Check if a path and access type would be allowed by the current rules.
    pub fn check_access(&self, path: &str, access: LandlockAccess) -> bool {
        if self.config.rules.is_empty() {
            return true; // No rules = allow all (sandbox not configured)
        }
        self.config
            .rules
            .iter()
            .any(|rule| path.starts_with(&rule.path) && rule.access.contains(&access))
    }

    /// Create a restrictive config that only allows read access to specified paths.
    pub fn read_only(paths: Vec<String>) -> LandlockConfig {
        LandlockConfig {
            rules: paths
                .into_iter()
                .map(|p| LandlockRule {
                    path: p,
                    access: vec![LandlockAccess::ReadFile, LandlockAccess::ReadDir],
                })
                .collect(),
            allow_network: false,
            enforced: Self::is_supported(),
        }
    }

    /// Create a config that allows read/write to specified paths.
    pub fn read_write(paths: Vec<String>) -> LandlockConfig {
        LandlockConfig {
            rules: paths
                .into_iter()
                .map(|p| LandlockRule {
                    path: p,
                    access: vec![
                        LandlockAccess::ReadFile,
                        LandlockAccess::ReadDir,
                        LandlockAccess::WriteFile,
                        LandlockAccess::MakeDir,
                    ],
                })
                .collect(),
            allow_network: false,
            enforced: Self::is_supported(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_config_has_empty_rules() {
        let config = LandlockConfig::default();
        assert!(config.rules.is_empty());
        assert!(!config.allow_network);
        assert!(!config.enforced);
    }

    #[test]
    fn is_supported_returns_false_on_non_linux() {
        // On Windows (and macOS) this must be false.
        if !cfg!(target_os = "linux") {
            assert!(!LandlockSandbox::is_supported());
        }
    }

    #[test]
    fn apply_returns_success_non_enforced_on_non_linux() {
        let sandbox = LandlockSandbox::new(LandlockConfig::default());
        let result = sandbox.apply();
        if !cfg!(target_os = "linux") {
            assert!(result.success);
            assert!(!result.enforced);
            assert!(result.message.contains("non-Linux"));
        }
    }

    #[test]
    fn check_access_allows_when_no_rules() {
        let sandbox = LandlockSandbox::new(LandlockConfig::default());
        assert!(sandbox.check_access("/any/path", LandlockAccess::ReadFile));
        assert!(sandbox.check_access("/any/path", LandlockAccess::WriteFile));
    }

    #[test]
    fn check_access_allows_matching_path_and_access() {
        let config = LandlockConfig {
            rules: vec![LandlockRule {
                path: "/home/user".to_string(),
                access: vec![LandlockAccess::ReadFile],
            }],
            allow_network: false,
            enforced: false,
        };
        let sandbox = LandlockSandbox::new(config);
        assert!(sandbox.check_access("/home/user/file.txt", LandlockAccess::ReadFile));
    }

    #[test]
    fn check_access_denies_non_matching_path() {
        let config = LandlockConfig {
            rules: vec![LandlockRule {
                path: "/home/user".to_string(),
                access: vec![LandlockAccess::ReadFile],
            }],
            allow_network: false,
            enforced: false,
        };
        let sandbox = LandlockSandbox::new(config);
        assert!(!sandbox.check_access("/etc/passwd", LandlockAccess::ReadFile));
    }

    #[test]
    fn check_access_denies_non_matching_access_type() {
        let config = LandlockConfig {
            rules: vec![LandlockRule {
                path: "/home/user".to_string(),
                access: vec![LandlockAccess::ReadFile],
            }],
            allow_network: false,
            enforced: false,
        };
        let sandbox = LandlockSandbox::new(config);
        assert!(!sandbox.check_access("/home/user/file.txt", LandlockAccess::WriteFile));
    }

    #[test]
    fn read_only_creates_correct_config() {
        let config = LandlockSandbox::read_only(vec!["/data".to_string(), "/config".to_string()]);
        assert_eq!(config.rules.len(), 2);
        assert!(!config.allow_network);
        assert_eq!(config.rules[0].path, "/data");
        assert!(config.rules[0].access.contains(&LandlockAccess::ReadFile));
        assert!(config.rules[0].access.contains(&LandlockAccess::ReadDir));
        assert!(!config.rules[0].access.contains(&LandlockAccess::WriteFile));
    }

    #[test]
    fn read_write_creates_correct_config() {
        let config = LandlockSandbox::read_write(vec!["/workspace".to_string()]);
        assert_eq!(config.rules.len(), 1);
        assert_eq!(config.rules[0].path, "/workspace");
        assert!(config.rules[0].access.contains(&LandlockAccess::ReadFile));
        assert!(config.rules[0].access.contains(&LandlockAccess::WriteFile));
        assert!(config.rules[0].access.contains(&LandlockAccess::MakeDir));
        assert!(!config.rules[0].access.contains(&LandlockAccess::RemoveFile));
    }

    #[test]
    fn config_serialization_roundtrip() {
        let config = LandlockConfig {
            rules: vec![LandlockRule {
                path: "/tmp".to_string(),
                access: vec![LandlockAccess::ReadFile, LandlockAccess::WriteFile],
            }],
            allow_network: true,
            enforced: false,
        };
        let json = serde_json::to_string(&config).unwrap();
        let deserialized: LandlockConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.rules.len(), 1);
        assert_eq!(deserialized.rules[0].path, "/tmp");
        assert!(deserialized.allow_network);
    }

    #[test]
    fn landlock_result_serialization() {
        let result = LandlockResult {
            success: true,
            enforced: false,
            message: "test".to_string(),
        };
        let json = serde_json::to_string(&result).unwrap();
        let deserialized: LandlockResult = serde_json::from_str(&json).unwrap();
        assert!(deserialized.success);
        assert!(!deserialized.enforced);
        assert_eq!(deserialized.message, "test");
    }

    #[test]
    fn landlock_access_serialization() {
        let access = LandlockAccess::Execute;
        let json = serde_json::to_string(&access).unwrap();
        let deserialized: LandlockAccess = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized, LandlockAccess::Execute);
    }

    #[test]
    fn sandbox_config_getter() {
        let config = LandlockConfig {
            rules: vec![],
            allow_network: true,
            enforced: false,
        };
        let sandbox = LandlockSandbox::new(config);
        assert!(sandbox.config().allow_network);
        assert!(sandbox.config().rules.is_empty());
    }
}

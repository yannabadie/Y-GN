//! Process-based sandbox engine.
//!
//! Provides WASM-like access restrictions using process-level checks.
//! Each [`SandboxProfile`] defines a set of allowed and denied operations,
//! and [`ProcessSandbox::check_access`] validates requests against the profile.

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// The kind of access being requested.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum AccessKind {
    /// Network access (HTTP, TCP, etc.).
    Network,
    /// Read a file from the filesystem.
    FileRead,
    /// Write a file to the filesystem.
    FileWrite,
    /// Execute a shell command.
    Command,
}

/// A request to perform a sandboxed operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccessRequest {
    /// The kind of access being requested.
    pub kind: AccessKind,
    /// The target of the access (URL, file path, command name).
    pub target: String,
}

/// The result of a sandbox access check.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccessResult {
    /// Whether the access is allowed.
    pub allowed: bool,
    /// Human-readable reason for the decision.
    pub reason: String,
    /// The profile that produced this decision.
    pub profile: String,
}

/// Sandbox profile controlling which operations are permitted.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum SandboxProfile {
    /// No network access allowed.
    NoNet,
    /// Network access is permitted.
    Net,
    /// Filesystem is read-only.
    ReadOnlyFs,
    /// Writes allowed only within the scratch directory.
    ScratchFs,
}

// ---------------------------------------------------------------------------
// Trait for policy engine integration
// ---------------------------------------------------------------------------

/// Trait abstraction so the policy engine can check sandbox rules without
/// depending on a concrete type.
pub trait SandboxChecker: Send + Sync {
    fn check_access(&self, request: &AccessRequest) -> AccessResult;
    fn profile_name(&self) -> &str;
}

// ---------------------------------------------------------------------------
// ProcessSandbox
// ---------------------------------------------------------------------------

/// A process-level sandbox that enforces access restrictions based on a
/// [`SandboxProfile`].
#[derive(Debug, Clone)]
pub struct ProcessSandbox {
    profile: SandboxProfile,
    allowed_paths: Vec<PathBuf>,
    scratch_dir: PathBuf,
}

impl ProcessSandbox {
    /// Create a new sandbox with the given profile.
    ///
    /// Uses a system temp directory as the default scratch dir.
    pub fn new(profile: SandboxProfile) -> Self {
        Self {
            profile,
            allowed_paths: vec![],
            scratch_dir: std::env::temp_dir().join("ygn-sandbox"),
        }
    }

    /// Add an allowed path for file-read operations.
    pub fn allow_path(&mut self, path: PathBuf) {
        self.allowed_paths.push(path);
    }

    /// Set the scratch directory for `ScratchFs` profile.
    pub fn set_scratch_dir(&mut self, dir: PathBuf) {
        self.scratch_dir = dir;
    }

    /// Validate whether an access request is allowed under this sandbox's
    /// profile. This is the core enforcement point.
    pub fn check_access(&self, request: &AccessRequest) -> AccessResult {
        match &request.kind {
            AccessKind::Network => self.check_network(request),
            AccessKind::FileRead => self.check_file_read(request),
            AccessKind::FileWrite => self.check_file_write(request),
            AccessKind::Command => self.check_command(request),
        }
    }

    // -- internal checks ---------------------------------------------------

    fn check_network(&self, _request: &AccessRequest) -> AccessResult {
        match self.profile {
            SandboxProfile::NoNet => AccessResult {
                allowed: false,
                reason: "Network access is blocked by NoNet profile".into(),
                profile: self.profile_label().into(),
            },
            _ => AccessResult {
                allowed: true,
                reason: "Network access permitted".into(),
                profile: self.profile_label().into(),
            },
        }
    }

    fn check_file_read(&self, request: &AccessRequest) -> AccessResult {
        // Path traversal check first.
        if self.has_traversal(&request.target) {
            return AccessResult {
                allowed: false,
                reason: "Path traversal detected — access denied".into(),
                profile: self.profile_label().into(),
            };
        }

        // If allowed_paths is empty, permit all reads.
        if self.allowed_paths.is_empty() {
            return AccessResult {
                allowed: true,
                reason: "No path restrictions configured — read allowed".into(),
                profile: self.profile_label().into(),
            };
        }

        let target = Path::new(&request.target);
        if self.is_within_allowed_paths(target) {
            AccessResult {
                allowed: true,
                reason: "Path is within allowed paths".into(),
                profile: self.profile_label().into(),
            }
        } else {
            AccessResult {
                allowed: false,
                reason: format!("Path '{}' is not within any allowed path", request.target),
                profile: self.profile_label().into(),
            }
        }
    }

    fn check_file_write(&self, request: &AccessRequest) -> AccessResult {
        // Path traversal check first.
        if self.has_traversal(&request.target) {
            return AccessResult {
                allowed: false,
                reason: "Path traversal detected — access denied".into(),
                profile: self.profile_label().into(),
            };
        }

        match self.profile {
            SandboxProfile::ReadOnlyFs => AccessResult {
                allowed: false,
                reason: "File writes are blocked by ReadOnlyFs profile".into(),
                profile: self.profile_label().into(),
            },
            SandboxProfile::ScratchFs => {
                let target = Path::new(&request.target);
                if target.starts_with(&self.scratch_dir) {
                    AccessResult {
                        allowed: true,
                        reason: "Write within scratch directory is allowed".into(),
                        profile: self.profile_label().into(),
                    }
                } else {
                    AccessResult {
                        allowed: false,
                        reason: format!(
                            "ScratchFs profile only allows writes under '{}'",
                            self.scratch_dir.display()
                        ),
                        profile: self.profile_label().into(),
                    }
                }
            }
            _ => {
                // For NoNet and Net profiles, file writes are allowed
                // (they only restrict network, not filesystem).
                AccessResult {
                    allowed: true,
                    reason: "File write permitted by current profile".into(),
                    profile: self.profile_label().into(),
                }
            }
        }
    }

    fn check_command(&self, _request: &AccessRequest) -> AccessResult {
        // Commands are allowed by all profiles — the policy engine handles
        // higher-level tool approval. The sandbox only enforces I/O
        // restrictions.
        AccessResult {
            allowed: true,
            reason: "Command execution permitted by sandbox (policy engine may add further checks)"
                .into(),
            profile: self.profile_label().into(),
        }
    }

    // -- helpers -----------------------------------------------------------

    /// Detect directory-traversal attempts (`..` segments).
    fn has_traversal(&self, path_str: &str) -> bool {
        let path = Path::new(path_str);
        for component in path.components() {
            if let std::path::Component::ParentDir = component {
                return true;
            }
        }
        false
    }

    /// Check whether `target` is within any of the allowed paths.
    fn is_within_allowed_paths(&self, target: &Path) -> bool {
        self.allowed_paths.iter().any(|p| target.starts_with(p))
    }

    fn profile_label(&self) -> &str {
        match self.profile {
            SandboxProfile::NoNet => "NoNet",
            SandboxProfile::Net => "Net",
            SandboxProfile::ReadOnlyFs => "ReadOnlyFs",
            SandboxProfile::ScratchFs => "ScratchFs",
        }
    }
}

impl SandboxChecker for ProcessSandbox {
    fn check_access(&self, request: &AccessRequest) -> AccessResult {
        self.check_access(request)
    }

    fn profile_name(&self) -> &str {
        self.profile_label()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -- NoNet profile -----------------------------------------------------

    #[test]
    fn nonet_blocks_network_access() {
        let sandbox = ProcessSandbox::new(SandboxProfile::NoNet);
        let req = AccessRequest {
            kind: AccessKind::Network,
            target: "https://example.com".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(!result.allowed);
        assert!(result.reason.contains("NoNet"));
    }

    #[test]
    fn nonet_allows_file_read() {
        let sandbox = ProcessSandbox::new(SandboxProfile::NoNet);
        let req = AccessRequest {
            kind: AccessKind::FileRead,
            target: "/tmp/data.txt".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(result.allowed);
    }

    // -- Net profile -------------------------------------------------------

    #[test]
    fn net_allows_network_access() {
        let sandbox = ProcessSandbox::new(SandboxProfile::Net);
        let req = AccessRequest {
            kind: AccessKind::Network,
            target: "https://api.example.com".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(result.allowed);
    }

    // -- ReadOnlyFs profile ------------------------------------------------

    #[test]
    fn readonlyfs_blocks_file_write() {
        let sandbox = ProcessSandbox::new(SandboxProfile::ReadOnlyFs);
        let req = AccessRequest {
            kind: AccessKind::FileWrite,
            target: "/home/user/output.txt".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(!result.allowed);
        assert!(result.reason.contains("ReadOnlyFs"));
    }

    #[test]
    fn readonlyfs_allows_file_read() {
        let sandbox = ProcessSandbox::new(SandboxProfile::ReadOnlyFs);
        let req = AccessRequest {
            kind: AccessKind::FileRead,
            target: "/home/user/data.txt".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(result.allowed);
    }

    // -- ScratchFs profile -------------------------------------------------

    #[test]
    fn scratchfs_allows_write_within_scratch() {
        let mut sandbox = ProcessSandbox::new(SandboxProfile::ScratchFs);
        sandbox.set_scratch_dir(PathBuf::from("/tmp/scratch"));
        let req = AccessRequest {
            kind: AccessKind::FileWrite,
            target: "/tmp/scratch/output.txt".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(result.allowed);
    }

    #[test]
    fn scratchfs_blocks_write_outside_scratch() {
        let mut sandbox = ProcessSandbox::new(SandboxProfile::ScratchFs);
        sandbox.set_scratch_dir(PathBuf::from("/tmp/scratch"));
        let req = AccessRequest {
            kind: AccessKind::FileWrite,
            target: "/home/user/output.txt".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(!result.allowed);
        assert!(result.reason.contains("ScratchFs"));
    }

    // -- Path traversal prevention -----------------------------------------

    #[test]
    fn path_traversal_blocked_on_read() {
        let mut sandbox = ProcessSandbox::new(SandboxProfile::Net);
        sandbox.allow_path(PathBuf::from("/home/user/project"));
        let req = AccessRequest {
            kind: AccessKind::FileRead,
            target: "/home/user/project/../../../etc/passwd".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(!result.allowed);
        assert!(result.reason.contains("traversal"));
    }

    #[test]
    fn path_traversal_blocked_on_write() {
        let sandbox = ProcessSandbox::new(SandboxProfile::Net);
        let req = AccessRequest {
            kind: AccessKind::FileWrite,
            target: "/tmp/../etc/shadow".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(!result.allowed);
        assert!(result.reason.contains("traversal"));
    }

    // -- Allowed-paths enforcement -----------------------------------------

    #[test]
    fn file_read_within_allowed_path() {
        let mut sandbox = ProcessSandbox::new(SandboxProfile::Net);
        sandbox.allow_path(PathBuf::from("/home/user/project"));
        let req = AccessRequest {
            kind: AccessKind::FileRead,
            target: "/home/user/project/src/main.rs".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(result.allowed);
    }

    #[test]
    fn file_read_outside_allowed_path_denied() {
        let mut sandbox = ProcessSandbox::new(SandboxProfile::Net);
        sandbox.allow_path(PathBuf::from("/home/user/project"));
        let req = AccessRequest {
            kind: AccessKind::FileRead,
            target: "/etc/passwd".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(!result.allowed);
        assert!(result.reason.contains("not within"));
    }

    // -- Command access ----------------------------------------------------

    #[test]
    fn command_access_allowed_in_all_profiles() {
        for profile in [
            SandboxProfile::NoNet,
            SandboxProfile::Net,
            SandboxProfile::ReadOnlyFs,
            SandboxProfile::ScratchFs,
        ] {
            let sandbox = ProcessSandbox::new(profile);
            let req = AccessRequest {
                kind: AccessKind::Command,
                target: "ls".into(),
            };
            let result = sandbox.check_access(&req);
            assert!(result.allowed, "Command should be allowed in all profiles");
        }
    }

    // -- No allowed paths configured => all reads pass ---------------------

    #[test]
    fn no_path_restrictions_allows_any_read() {
        let sandbox = ProcessSandbox::new(SandboxProfile::Net);
        // No allow_path calls — should permit everything.
        let req = AccessRequest {
            kind: AccessKind::FileRead,
            target: "/anywhere/at/all".into(),
        };
        let result = sandbox.check_access(&req);
        assert!(result.allowed);
    }

    // -- SandboxChecker trait works ----------------------------------------

    #[test]
    fn sandbox_checker_trait_delegates() {
        let sandbox = ProcessSandbox::new(SandboxProfile::NoNet);
        let checker: &dyn SandboxChecker = &sandbox;
        let req = AccessRequest {
            kind: AccessKind::Network,
            target: "https://evil.com".into(),
        };
        let result = checker.check_access(&req);
        assert!(!result.allowed);
        assert_eq!(checker.profile_name(), "NoNet");
    }
}

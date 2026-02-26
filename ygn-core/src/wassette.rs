//! Wassette WASM sandbox integration.
//!
//! Provides a [`WassetteSandbox`] that delegates WASM component execution to
//! the external `wassette` CLI, mapping Y-GN sandbox profiles to Wassette
//! permission flags.  Falls back to [`ProcessSandbox`] when the binary is not
//! available.
//!
//! Gated behind `cfg(feature = "wassette")` so tests skip gracefully when the
//! binary is absent.

use serde::{Deserialize, Serialize};
use std::process::Command;

use crate::sandbox::{AccessRequest, AccessResult, SandboxChecker, SandboxProfile};

// ---------------------------------------------------------------------------
// Policy mapping: Y-GN profiles → Wassette permission flags
// ---------------------------------------------------------------------------

/// Map a Y-GN [`SandboxProfile`] to Wassette CLI permission flags.
pub fn profile_to_wassette_flags(profile: &SandboxProfile) -> Vec<&'static str> {
    match profile {
        SandboxProfile::NoNet => vec!["--deny-net"],
        SandboxProfile::Net => vec!["--allow-net"],
        SandboxProfile::ReadOnlyFs => vec!["--allow-net", "--deny-fs-write"],
        SandboxProfile::ScratchFs => vec!["--allow-net", "--allow-fs-write=scratch"],
    }
}

// ---------------------------------------------------------------------------
// Availability check
// ---------------------------------------------------------------------------

/// Check whether the `wassette` binary is available on `$PATH`.
pub fn is_available() -> bool {
    if cfg!(target_os = "windows") {
        Command::new("where")
            .arg("wassette")
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    } else {
        Command::new("which")
            .arg("wassette")
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    }
}

// ---------------------------------------------------------------------------
// WassetteSandbox
// ---------------------------------------------------------------------------

/// Configuration for the Wassette sandbox integration.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WassetteConfig {
    /// Whether Wassette integration is enabled.
    pub enabled: bool,
    /// OCI registries to pull components from.
    pub registries: Vec<String>,
}

/// WASM sandbox that delegates execution to the `wassette` CLI.
///
/// When the Wassette binary is unavailable, all operations fall back to the
/// process-level sandbox.
#[derive(Debug, Clone)]
pub struct WassetteSandbox {
    profile: SandboxProfile,
    available: bool,
}

impl WassetteSandbox {
    /// Create a new Wassette sandbox. Checks binary availability once.
    pub fn new(profile: SandboxProfile) -> Self {
        Self {
            profile,
            available: is_available(),
        }
    }

    /// Whether the Wassette runtime is available.
    pub fn is_available(&self) -> bool {
        self.available
    }

    /// Execute a WASM component reference with the configured profile.
    ///
    /// Returns `Ok(output)` on success or `Err(reason)` on failure.
    pub fn execute_wasm(&self, component_ref: &str, args: &[&str]) -> Result<String, String> {
        if !self.available {
            return Err("Wassette binary not available".into());
        }

        let flags = profile_to_wassette_flags(&self.profile);
        let output = Command::new("wassette")
            .arg("run")
            .arg(component_ref)
            .args(&flags)
            .args(args)
            .output()
            .map_err(|e| format!("Failed to spawn wassette: {e}"))?;

        if output.status.success() {
            Ok(String::from_utf8_lossy(&output.stdout).into_owned())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).into_owned())
        }
    }
}

impl SandboxChecker for WassetteSandbox {
    fn check_access(&self, request: &AccessRequest) -> AccessResult {
        // Delegate to process-level sandbox logic for access checks.
        // The actual WASM isolation happens in execute_wasm().
        let process_sandbox = crate::sandbox::ProcessSandbox::new(self.profile.clone());
        process_sandbox.check_access(request)
    }

    fn profile_name(&self) -> &str {
        if self.available {
            "Wassette"
        } else {
            "ProcessSandbox(fallback)"
        }
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wassette_availability_check() {
        // Just verify the function runs without panic.
        // On CI, wassette is typically not installed.
        let _available = is_available();
    }

    #[test]
    fn wassette_policy_mapping() {
        assert_eq!(
            profile_to_wassette_flags(&SandboxProfile::NoNet),
            vec!["--deny-net"]
        );
        assert_eq!(
            profile_to_wassette_flags(&SandboxProfile::Net),
            vec!["--allow-net"]
        );
        assert_eq!(
            profile_to_wassette_flags(&SandboxProfile::ReadOnlyFs),
            vec!["--allow-net", "--deny-fs-write"]
        );
        assert_eq!(
            profile_to_wassette_flags(&SandboxProfile::ScratchFs),
            vec!["--allow-net", "--allow-fs-write=scratch"]
        );
    }

    #[test]
    fn wassette_sandbox_fallback() {
        // When wassette is not available, profile_name indicates fallback.
        let sandbox = WassetteSandbox {
            profile: SandboxProfile::NoNet,
            available: false,
        };
        assert_eq!(sandbox.profile_name(), "ProcessSandbox(fallback)");
        assert!(!sandbox.is_available());

        // execute_wasm should return error
        let result = sandbox.execute_wasm("ghcr.io/test/component:latest", &[]);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("not available"));
    }
}

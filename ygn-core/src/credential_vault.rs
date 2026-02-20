//! Secure credential vault for provider API keys.
//!
//! Stores API keys and tokens in memory with zeroization on drop.
//! Keys are loaded from environment variables and never exposed
//! through Debug or logging.

use std::collections::HashMap;
use std::fmt;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Secure storage for provider API keys and credentials.
/// Keys are loaded from environment variables and stored in memory.
/// Implements zero-copy access patterns to minimize key exposure.
pub struct CredentialVault {
    credentials: HashMap<String, SecureCredential>,
}

/// A single credential entry.
pub struct SecureCredential {
    /// Provider name (e.g., "claude", "openai", "gemini")
    provider: String,
    /// The actual secret value (API key, token, etc.)
    /// Stored as Vec<u8> to allow zeroization on drop.
    secret: Vec<u8>,
    /// When this credential was loaded.
    loaded_at: chrono::DateTime<chrono::Utc>,
    /// Optional expiry.
    expires_at: Option<chrono::DateTime<chrono::Utc>>,
}

// ---------------------------------------------------------------------------
// SecureCredential — Drop zeroes memory
// ---------------------------------------------------------------------------

impl Drop for SecureCredential {
    fn drop(&mut self) {
        // Zero out every byte of the secret before freeing.
        for byte in self.secret.iter_mut() {
            // Use write_volatile to prevent the compiler from optimizing away
            // the zeroing.
            unsafe {
                std::ptr::write_volatile(byte as *mut u8, 0);
            }
        }
    }
}

// ---------------------------------------------------------------------------
// SecureCredential — Debug NEVER leaks the secret
// ---------------------------------------------------------------------------

impl fmt::Debug for SecureCredential {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("SecureCredential")
            .field("provider", &self.provider)
            .field("secret", &"***")
            .field("loaded_at", &self.loaded_at)
            .field("expires_at", &self.expires_at)
            .finish()
    }
}

// ---------------------------------------------------------------------------
// SecureCredential impl
// ---------------------------------------------------------------------------

impl SecureCredential {
    /// Create a new credential.
    fn new(provider: &str, secret: &str) -> Self {
        Self {
            provider: provider.to_string(),
            secret: secret.as_bytes().to_vec(),
            loaded_at: chrono::Utc::now(),
            expires_at: None,
        }
    }

    /// Return the secret as a UTF-8 string slice.
    fn secret_str(&self) -> Option<&str> {
        std::str::from_utf8(&self.secret).ok()
    }

    /// Return a redacted representation, showing only the first 8 characters
    /// (or fewer if the key is short) followed by "***".
    fn redacted(&self) -> String {
        let s = self.secret_str().unwrap_or("");
        let prefix_len = s.len().min(8);
        format!("{}***", &s[..prefix_len])
    }
}

// ---------------------------------------------------------------------------
// Well-known environment variable mappings
// ---------------------------------------------------------------------------

/// (env_var, provider_name)
const ENV_MAPPINGS: &[(&str, &str)] = &[
    ("ANTHROPIC_API_KEY", "claude"),
    ("OPENAI_API_KEY", "openai"),
    ("GEMINI_API_KEY", "gemini"),
    ("OLLAMA_BASE_URL", "ollama"),
];

// ---------------------------------------------------------------------------
// CredentialVault impl
// ---------------------------------------------------------------------------

impl CredentialVault {
    /// Create an empty vault.
    pub fn new() -> Self {
        Self {
            credentials: HashMap::new(),
        }
    }

    /// Scan well-known environment variables and load any that are set.
    pub fn from_env() -> Self {
        let mut vault = Self::new();
        for &(env_var, provider) in ENV_MAPPINGS {
            if let Ok(value) = std::env::var(env_var) {
                if !value.is_empty() {
                    vault.credentials.insert(
                        provider.to_string(),
                        SecureCredential::new(provider, &value),
                    );
                }
            }
        }
        vault
    }

    /// Get the API key / URL for a provider.
    pub fn get(&self, provider: &str) -> Option<&str> {
        self.credentials.get(provider).and_then(|c| c.secret_str())
    }

    /// Check whether a credential exists for the given provider.
    pub fn has(&self, provider: &str) -> bool {
        self.credentials.contains_key(provider)
    }

    /// List providers that have credentials loaded.
    pub fn available_providers(&self) -> Vec<&str> {
        self.credentials.keys().map(|k| k.as_str()).collect()
    }

    /// Manually add or replace a credential.
    pub fn set(&mut self, provider: &str, key: &str) {
        self.credentials
            .insert(provider.to_string(), SecureCredential::new(provider, key));
    }

    /// Remove a credential. Returns `true` if it existed.
    pub fn remove(&mut self, provider: &str) -> bool {
        self.credentials.remove(provider).is_some()
    }

    /// Produce a summary string that shows each provider and a redacted key
    /// prefix. Suitable for logging.
    pub fn redacted_summary(&self) -> String {
        let mut lines: Vec<String> = self
            .credentials
            .iter()
            .map(|(name, cred)| format!("{}: {}", name, cred.redacted()))
            .collect();
        lines.sort(); // deterministic output
        lines.join("\n")
    }
}

impl Default for CredentialVault {
    fn default() -> Self {
        Self::new()
    }
}

impl fmt::Debug for CredentialVault {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("CredentialVault")
            .field("providers", &self.available_providers())
            .finish()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn from_env_picks_up_set_vars() {
        // Set an env var, build vault, verify it is found.
        std::env::set_var("ANTHROPIC_API_KEY", "sk-ant-test-key-12345");
        let vault = CredentialVault::from_env();
        assert!(vault.has("claude"));
        assert_eq!(vault.get("claude"), Some("sk-ant-test-key-12345"));
        // Cleanup
        std::env::remove_var("ANTHROPIC_API_KEY");
    }

    #[test]
    fn get_returns_correct_key() {
        let mut vault = CredentialVault::new();
        vault.set("openai", "sk-openai-abc123");
        assert_eq!(vault.get("openai"), Some("sk-openai-abc123"));
    }

    #[test]
    fn get_returns_none_for_missing() {
        let vault = CredentialVault::new();
        assert_eq!(vault.get("nonexistent"), None);
    }

    #[test]
    fn has_checks_existence() {
        let mut vault = CredentialVault::new();
        assert!(!vault.has("claude"));
        vault.set("claude", "key123");
        assert!(vault.has("claude"));
    }

    #[test]
    fn available_providers_lists_all() {
        let mut vault = CredentialVault::new();
        vault.set("claude", "k1");
        vault.set("openai", "k2");
        vault.set("gemini", "k3");
        let mut providers = vault.available_providers();
        providers.sort();
        assert_eq!(providers, vec!["claude", "gemini", "openai"]);
    }

    #[test]
    fn redacted_summary_never_shows_full_key() {
        let mut vault = CredentialVault::new();
        vault.set("claude", "sk-ant-api03-very-long-secret-key-value");
        let summary = vault.redacted_summary();
        assert!(summary.contains("claude: sk-ant-a***"));
        assert!(!summary.contains("very-long-secret-key-value"));
    }

    #[test]
    fn set_and_remove_work() {
        let mut vault = CredentialVault::new();
        vault.set("test-provider", "secret123");
        assert!(vault.has("test-provider"));
        assert_eq!(vault.get("test-provider"), Some("secret123"));

        let removed = vault.remove("test-provider");
        assert!(removed);
        assert!(!vault.has("test-provider"));

        // Removing again returns false
        assert!(!vault.remove("test-provider"));
    }

    #[test]
    fn debug_impl_never_shows_secret() {
        let cred = SecureCredential::new("claude", "super-secret-key");
        let debug_output = format!("{:?}", cred);
        assert!(debug_output.contains("***"));
        assert!(!debug_output.contains("super-secret-key"));
    }

    #[test]
    fn drop_zeros_out_secret_bytes() {
        use std::sync::Arc;

        // We allocate a credential, take a raw pointer to the secret buffer,
        // then drop the credential and verify the bytes are zeroed.
        let cred = SecureCredential::new("test", "MY_SECRET");
        let secret_ptr = cred.secret.as_ptr();
        let secret_len = cred.secret.len();

        // Copy original bytes for comparison
        let original: Vec<u8> = cred.secret.clone();
        assert_eq!(original, b"MY_SECRET");

        // Drop the credential — this should zero the buffer.
        drop(cred);

        // Read the memory through the raw pointer. After drop + zeroization
        // the bytes should be zero. Note: this is technically UB if the
        // allocator has already freed and reused the page, but in practice
        // for a test this works reliably.
        let zeroed: Vec<u8> =
            unsafe { std::slice::from_raw_parts(secret_ptr, secret_len).to_vec() };

        // We use Arc just to ensure the import compiles; the real check:
        let _arc_unused = Arc::new(0);
        assert!(
            zeroed.iter().all(|&b| b == 0),
            "Secret bytes were not zeroed on drop: {:?}",
            zeroed
        );
    }

    #[test]
    fn vault_debug_does_not_leak_keys() {
        let mut vault = CredentialVault::new();
        vault.set("claude", "secret-key-value-12345");
        let debug_output = format!("{:?}", vault);
        assert!(!debug_output.contains("secret-key-value-12345"));
        assert!(debug_output.contains("claude"));
    }
}

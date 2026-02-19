//! Auto-diagnostic build/runtime engine.
//!
//! When a quality gate fails the system automatically collects diagnostics,
//! classifies the error, proposes a fix, and can re-run the gates.
//! Implements EvoConfig-inspired self-healing for the Y-GN build pipeline.

use chrono::{DateTime, Utc};
use regex::Regex;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Classification of an error produced by a quality gate.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ErrorCategory {
    /// Missing crate or Python package.
    DependencyMissing,
    /// Rust/Python syntax or type error.
    CompilationError,
    /// One or more tests fail.
    TestFailure,
    /// fmt/clippy/ruff issue.
    LintViolation,
    /// Invalid configuration.
    ConfigurationError,
    /// Crash/panic at runtime.
    RuntimePanic,
    /// Unclassifiable error.
    Unknown,
}

/// A single diagnostic produced by analyzing gate output.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Diagnostic {
    /// Unique identifier (UUID).
    pub id: String,
    /// When the diagnostic was created.
    pub timestamp: DateTime<Utc>,
    /// Classification of the error.
    pub category: ErrorCategory,
    /// Which gate/process produced the error.
    pub source: String,
    /// Raw error output.
    pub message: String,
    /// Heuristic fix suggestion, if available.
    pub suggested_fix: Option<String>,
    /// Whether this error can be automatically fixed.
    pub auto_fixable: bool,
}

/// Result from running a single quality gate.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GateResult {
    /// Name of the gate (e.g. "cargo fmt --check").
    pub gate_name: String,
    /// Whether the gate passed.
    pub success: bool,
    /// Combined stdout+stderr output.
    pub output: String,
    /// Wall-clock duration in milliseconds.
    pub duration_ms: u64,
    /// Diagnostic populated on failure.
    pub diagnostic: Option<Diagnostic>,
}

/// An action the self-healing system can take to fix a diagnostic.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealAction {
    /// ID of the diagnostic this action addresses.
    pub diagnostic_id: String,
    /// Shell command to execute.
    pub command: String,
    /// Human-readable description of the action.
    pub description: String,
}

// ---------------------------------------------------------------------------
// DiagnosticEngine
// ---------------------------------------------------------------------------

/// Analyzes raw gate output and produces structured diagnostics.
#[derive(Debug, Clone)]
pub struct DiagnosticEngine {
    _private: (),
}

impl DiagnosticEngine {
    /// Create a new diagnostic engine.
    pub fn new() -> Self {
        Self { _private: () }
    }

    /// Analyze raw gate output, classify the error, and produce a diagnostic.
    pub fn analyze(&self, source: &str, raw_output: &str) -> Diagnostic {
        let category = Self::classify(raw_output);
        let mut diag = Diagnostic {
            id: uuid::Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            category: category.clone(),
            source: source.to_string(),
            message: raw_output.to_string(),
            suggested_fix: None,
            auto_fixable: false,
        };
        diag.suggested_fix = self.suggest_fix(&diag);
        diag.auto_fixable = Self::is_auto_fixable(&diag);
        diag
    }

    /// Classify a raw error string into an [`ErrorCategory`].
    fn classify(raw_output: &str) -> ErrorCategory {
        // Compilation errors: Rust "error[E" pattern
        if raw_output.contains("error[E") {
            return ErrorCategory::CompilationError;
        }

        // Dependency missing: "could not find" or "no matching package"
        if raw_output.contains("could not find")
            || raw_output.contains("no matching package")
            || raw_output.contains("ModuleNotFoundError")
        {
            return ErrorCategory::DependencyMissing;
        }

        // Test failures: "test result: FAILED" or "FAILED" in test output
        if raw_output.contains("test result: FAILED") || raw_output.contains("FAILED") {
            return ErrorCategory::TestFailure;
        }

        // Lint violations: "Diff in" (cargo fmt) or "warning:" (clippy/ruff)
        if raw_output.contains("Diff in") || raw_output.contains("warning:") {
            return ErrorCategory::LintViolation;
        }

        // Runtime panics: "panicked" or "thread '<name>' panicked"
        if raw_output.contains("panicked") {
            return ErrorCategory::RuntimePanic;
        }
        let panic_re = Regex::new(r"thread\s+'.*'\s+panicked").unwrap();
        if panic_re.is_match(raw_output) {
            return ErrorCategory::RuntimePanic;
        }

        // Configuration errors
        if raw_output.contains("invalid configuration")
            || raw_output.contains("config error")
            || raw_output.contains("missing required field")
            || raw_output.contains("ConfigurationError")
        {
            return ErrorCategory::ConfigurationError;
        }

        ErrorCategory::Unknown
    }

    /// Produce a heuristic fix suggestion for the given diagnostic.
    pub fn suggest_fix(&self, diagnostic: &Diagnostic) -> Option<String> {
        match diagnostic.category {
            ErrorCategory::DependencyMissing => {
                Some("Run `cargo add <crate>` or `pip install <package>`".to_string())
            }
            ErrorCategory::LintViolation => {
                if diagnostic.source.contains("fmt") {
                    Some("Run `cargo fmt` to auto-fix".to_string())
                } else if diagnostic.source.contains("ruff") {
                    Some("Run `ruff check --fix`".to_string())
                } else if diagnostic.source.contains("clippy") {
                    Some(
                        "Review clippy warnings and apply suggested fixes with `cargo clippy --fix`"
                            .to_string(),
                    )
                } else {
                    Some("Review lint warnings and apply fixes".to_string())
                }
            }
            ErrorCategory::TestFailure => {
                Some("Review failing test output and fix the assertion".to_string())
            }
            ErrorCategory::CompilationError => {
                Some("Check the compiler error message for type/syntax fix".to_string())
            }
            ErrorCategory::RuntimePanic => {
                Some("Examine the panic backtrace and fix the root cause".to_string())
            }
            ErrorCategory::ConfigurationError => {
                Some("Review and correct the configuration file".to_string())
            }
            ErrorCategory::Unknown => None,
        }
    }

    /// Returns `true` when the error can be auto-fixed (lint violations from
    /// fmt/ruff are auto-fixable).
    pub fn is_auto_fixable(diagnostic: &Diagnostic) -> bool {
        if diagnostic.category != ErrorCategory::LintViolation {
            return false;
        }
        diagnostic.source.contains("fmt") || diagnostic.source.contains("ruff")
    }
}

impl Default for DiagnosticEngine {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// GateRunner
// ---------------------------------------------------------------------------

/// Runs quality-gate commands and collects diagnostics on failure.
#[derive(Debug, Clone)]
pub struct GateRunner {
    engine: DiagnosticEngine,
}

impl GateRunner {
    /// Create a new gate runner.
    pub fn new() -> Self {
        Self {
            engine: DiagnosticEngine::new(),
        }
    }

    /// Run a single quality gate by executing a shell command.
    ///
    /// Captures stdout+stderr, measures wall-clock time, and produces a
    /// [`GateResult`] with an optional diagnostic on failure.
    pub fn run_gate(&self, name: &str, command: &str) -> GateResult {
        let start = std::time::Instant::now();

        let output = std::process::Command::new("sh")
            .arg("-c")
            .arg(command)
            .output();

        let elapsed = start.elapsed().as_millis() as u64;

        match output {
            Ok(out) => {
                let stdout = String::from_utf8_lossy(&out.stdout);
                let stderr = String::from_utf8_lossy(&out.stderr);
                let combined = format!("{}{}", stdout, stderr);
                let success = out.status.success();

                let diagnostic = if success {
                    None
                } else {
                    Some(self.engine.analyze(name, &combined))
                };

                GateResult {
                    gate_name: name.to_string(),
                    success,
                    output: combined,
                    duration_ms: elapsed,
                    diagnostic,
                }
            }
            Err(e) => {
                let error_msg = format!("Failed to execute command: {}", e);
                GateResult {
                    gate_name: name.to_string(),
                    success: false,
                    output: error_msg.clone(),
                    duration_ms: elapsed,
                    diagnostic: Some(self.engine.analyze(name, &error_msg)),
                }
            }
        }
    }

    /// Run the full quality-gate sequence.
    ///
    /// Gates:
    /// 1. `cargo fmt --check`
    /// 2. `cargo clippy -- -D warnings`
    /// 3. `cargo test`
    pub fn run_all_gates(&self) -> Vec<GateResult> {
        let gates = [
            ("cargo fmt --check", "cargo fmt --check"),
            ("cargo clippy", "cargo clippy -- -D warnings"),
            ("cargo test", "cargo test"),
        ];

        gates
            .iter()
            .map(|(name, cmd)| self.run_gate(name, cmd))
            .collect()
    }

    /// For auto-fixable diagnostics, return the commands needed to heal them.
    pub fn auto_heal(&self, diagnostics: &[Diagnostic]) -> Vec<HealAction> {
        diagnostics
            .iter()
            .filter(|d| DiagnosticEngine::is_auto_fixable(d))
            .map(|d| {
                let (command, description) = if d.source.contains("fmt") {
                    (
                        "cargo fmt".to_string(),
                        "Auto-format Rust source code".to_string(),
                    )
                } else if d.source.contains("ruff") {
                    (
                        "ruff check --fix".to_string(),
                        "Auto-fix Python lint violations".to_string(),
                    )
                } else {
                    (
                        "echo 'manual fix required'".to_string(),
                        "Manual intervention required".to_string(),
                    )
                };

                HealAction {
                    diagnostic_id: d.id.clone(),
                    command,
                    description,
                }
            })
            .collect()
    }
}

impl Default for GateRunner {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -- Classification tests -----------------------------------------------

    #[test]
    fn classify_compilation_error() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo build", "error[E0308]: mismatched types");
        assert_eq!(diag.category, ErrorCategory::CompilationError);
        assert_eq!(diag.source, "cargo build");
    }

    #[test]
    fn classify_dependency_missing() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze(
            "cargo build",
            "error: could not find `nonexistent` in the registry",
        );
        assert_eq!(diag.category, ErrorCategory::DependencyMissing);
    }

    #[test]
    fn classify_dependency_missing_python() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("pytest", "ModuleNotFoundError: No module named 'some_pkg'");
        assert_eq!(diag.category, ErrorCategory::DependencyMissing);
    }

    #[test]
    fn classify_test_failure() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze(
            "cargo test",
            "test result: FAILED. 1 passed; 2 failed; 0 ignored",
        );
        assert_eq!(diag.category, ErrorCategory::TestFailure);
    }

    #[test]
    fn classify_lint_violation() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze(
            "cargo fmt --check",
            "Diff in /src/main.rs at line 42:\n-    let x=1;\n+    let x = 1;",
        );
        assert_eq!(diag.category, ErrorCategory::LintViolation);
    }

    #[test]
    fn classify_clippy_warning() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze(
            "cargo clippy",
            "warning: unused variable: `x`\n  --> src/main.rs:5:9",
        );
        assert_eq!(diag.category, ErrorCategory::LintViolation);
    }

    #[test]
    fn classify_runtime_panic() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze(
            "cargo run",
            "thread 'main' panicked at 'index out of bounds'",
        );
        assert_eq!(diag.category, ErrorCategory::RuntimePanic);
    }

    #[test]
    fn classify_configuration_error() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze(
            "ygn-core config",
            "invalid configuration: missing field `node_role`",
        );
        assert_eq!(diag.category, ErrorCategory::ConfigurationError);
    }

    #[test]
    fn classify_unknown_error() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("some-gate", "something completely unexpected happened");
        assert_eq!(diag.category, ErrorCategory::Unknown);
    }

    // -- Fix suggestion tests -----------------------------------------------

    #[test]
    fn suggest_fix_for_fmt_lint() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo fmt --check", "Diff in /src/main.rs");
        assert_eq!(
            diag.suggested_fix.as_deref(),
            Some("Run `cargo fmt` to auto-fix")
        );
    }

    #[test]
    fn suggest_fix_for_ruff_lint() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("ruff check", "warning: unused import");
        assert_eq!(
            diag.suggested_fix.as_deref(),
            Some("Run `ruff check --fix`")
        );
    }

    #[test]
    fn suggest_fix_for_dependency() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo build", "could not find `foo` in registry");
        assert_eq!(
            diag.suggested_fix.as_deref(),
            Some("Run `cargo add <crate>` or `pip install <package>`")
        );
    }

    #[test]
    fn suggest_fix_for_compilation_error() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo build", "error[E0599]: no method named `foo`");
        assert_eq!(
            diag.suggested_fix.as_deref(),
            Some("Check the compiler error message for type/syntax fix")
        );
    }

    #[test]
    fn suggest_fix_for_test_failure() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo test", "test result: FAILED. 0 passed; 1 failed");
        assert_eq!(
            diag.suggested_fix.as_deref(),
            Some("Review failing test output and fix the assertion")
        );
    }

    #[test]
    fn suggest_fix_returns_none_for_unknown() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("mystery", "no idea what happened");
        assert!(diag.suggested_fix.is_none());
    }

    // -- Auto-fixable tests -------------------------------------------------

    #[test]
    fn auto_fixable_true_for_fmt_lint() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo fmt --check", "Diff in /src/main.rs");
        assert!(diag.auto_fixable);
    }

    #[test]
    fn auto_fixable_true_for_ruff_lint() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("ruff check", "warning: unused import");
        assert!(diag.auto_fixable);
    }

    #[test]
    fn auto_fixable_false_for_test_failure() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo test", "test result: FAILED. 0 passed; 3 failed");
        assert!(!diag.auto_fixable);
    }

    #[test]
    fn auto_fixable_false_for_clippy_lint() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo clippy", "warning: unused variable");
        assert!(!diag.auto_fixable);
    }

    // -- Struct construction tests ------------------------------------------

    #[test]
    fn gate_result_construction() {
        let result = GateResult {
            gate_name: "cargo test".to_string(),
            success: true,
            output: "test result: ok. 10 passed".to_string(),
            duration_ms: 1234,
            diagnostic: None,
        };
        assert!(result.success);
        assert_eq!(result.gate_name, "cargo test");
        assert!(result.diagnostic.is_none());
    }

    #[test]
    fn gate_result_with_diagnostic() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo test", "test result: FAILED. 1 passed; 2 failed");
        let result = GateResult {
            gate_name: "cargo test".to_string(),
            success: false,
            output: "test result: FAILED. 1 passed; 2 failed".to_string(),
            duration_ms: 5678,
            diagnostic: Some(diag),
        };
        assert!(!result.success);
        assert!(result.diagnostic.is_some());
        assert_eq!(
            result.diagnostic.unwrap().category,
            ErrorCategory::TestFailure
        );
    }

    #[test]
    fn heal_action_for_fmt_lint() {
        let runner = GateRunner::new();
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo fmt --check", "Diff in /src/main.rs");
        let actions = runner.auto_heal(&[diag]);
        assert_eq!(actions.len(), 1);
        assert_eq!(actions[0].command, "cargo fmt");
        assert_eq!(actions[0].description, "Auto-format Rust source code");
    }

    #[test]
    fn heal_action_for_ruff_lint() {
        let runner = GateRunner::new();
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("ruff check", "warning: unused import");
        let actions = runner.auto_heal(&[diag]);
        assert_eq!(actions.len(), 1);
        assert_eq!(actions[0].command, "ruff check --fix");
        assert_eq!(actions[0].description, "Auto-fix Python lint violations");
    }

    #[test]
    fn heal_action_skips_non_auto_fixable() {
        let runner = GateRunner::new();
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo test", "test result: FAILED. 0 passed; 1 failed");
        let actions = runner.auto_heal(&[diag]);
        assert!(actions.is_empty());
    }

    // -- Serialization roundtrip tests --------------------------------------

    #[test]
    fn diagnostic_serialization_roundtrip() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("cargo build", "error[E0308]: mismatched types");
        let json = serde_json::to_string(&diag).unwrap();
        let round: Diagnostic = serde_json::from_str(&json).unwrap();
        assert_eq!(round.category, ErrorCategory::CompilationError);
        assert_eq!(round.source, "cargo build");
    }

    #[test]
    fn error_category_serialization_roundtrip() {
        let categories = vec![
            ErrorCategory::DependencyMissing,
            ErrorCategory::CompilationError,
            ErrorCategory::TestFailure,
            ErrorCategory::LintViolation,
            ErrorCategory::ConfigurationError,
            ErrorCategory::RuntimePanic,
            ErrorCategory::Unknown,
        ];
        for cat in categories {
            let json = serde_json::to_string(&cat).unwrap();
            let round: ErrorCategory = serde_json::from_str(&json).unwrap();
            assert_eq!(round, cat);
        }
    }

    #[test]
    fn gate_result_serialization_roundtrip() {
        let result = GateResult {
            gate_name: "cargo clippy".to_string(),
            success: false,
            output: "warning: unused variable".to_string(),
            duration_ms: 999,
            diagnostic: None,
        };
        let json = serde_json::to_string(&result).unwrap();
        let round: GateResult = serde_json::from_str(&json).unwrap();
        assert_eq!(round.gate_name, "cargo clippy");
        assert!(!round.success);
    }

    #[test]
    fn heal_action_serialization_roundtrip() {
        let action = HealAction {
            diagnostic_id: "test-id-123".to_string(),
            command: "cargo fmt".to_string(),
            description: "Auto-format code".to_string(),
        };
        let json = serde_json::to_string(&action).unwrap();
        let round: HealAction = serde_json::from_str(&json).unwrap();
        assert_eq!(round.diagnostic_id, "test-id-123");
        assert_eq!(round.command, "cargo fmt");
    }

    #[test]
    fn diagnostic_has_valid_uuid() {
        let engine = DiagnosticEngine::new();
        let diag = engine.analyze("test", "some output");
        // UUID v4 format: 8-4-4-4-12 hex chars
        assert_eq!(diag.id.len(), 36);
        assert!(uuid::Uuid::parse_str(&diag.id).is_ok());
    }

    #[test]
    fn diagnostic_engine_default_trait() {
        let engine = DiagnosticEngine::default();
        let diag = engine.analyze("test", "error[E0308]: types");
        assert_eq!(diag.category, ErrorCategory::CompilationError);
    }

    #[test]
    fn gate_runner_default_trait() {
        let runner = GateRunner::default();
        let actions = runner.auto_heal(&[]);
        assert!(actions.is_empty());
    }
}

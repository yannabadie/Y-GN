//! Skills system.
//!
//! A skill is a higher-level abstraction over tools — it composes multiple
//! tool calls into a reusable workflow with dependency ordering.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::tool::ToolRegistry;

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

/// A single step within a skill workflow.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillStep {
    /// Name of the tool to invoke.
    pub tool_name: String,
    /// JSON arguments to pass to the tool.
    pub arguments: serde_json::Value,
    /// Human-readable description of what this step does.
    pub description: String,
    /// Indices of steps this step depends on (must complete first).
    pub depends_on: Vec<usize>,
}

/// Definition of a reusable skill.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillDefinition {
    pub name: String,
    pub description: String,
    pub version: String,
    pub author: String,
    pub steps: Vec<SkillStep>,
    pub tags: Vec<String>,
    pub created_at: DateTime<Utc>,
}

/// Result of executing a single step.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StepResult {
    pub step_index: usize,
    pub tool_name: String,
    pub success: bool,
    pub output: String,
    pub duration_ms: u64,
}

/// Result of executing an entire skill.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillExecution {
    pub skill_name: String,
    pub started_at: DateTime<Utc>,
    pub completed_at: Option<DateTime<Utc>>,
    pub step_results: Vec<StepResult>,
    pub overall_success: bool,
}

// ---------------------------------------------------------------------------
// SkillRegistry
// ---------------------------------------------------------------------------

/// Holds a collection of skill definitions and provides lookup / search.
#[derive(Debug, Default)]
pub struct SkillRegistry {
    skills: HashMap<String, SkillDefinition>,
}

impl SkillRegistry {
    /// Create an empty registry.
    pub fn new() -> Self {
        Self::default()
    }

    /// Register a skill. Returns an error if a skill with the same name
    /// already exists.
    pub fn register(&mut self, skill: SkillDefinition) -> anyhow::Result<()> {
        if self.skills.contains_key(&skill.name) {
            anyhow::bail!("skill '{}' is already registered", skill.name);
        }
        self.skills.insert(skill.name.clone(), skill);
        Ok(())
    }

    /// Look up a skill by name.
    pub fn get(&self, name: &str) -> Option<&SkillDefinition> {
        self.skills.get(name)
    }

    /// List all registered skills.
    pub fn list(&self) -> Vec<&SkillDefinition> {
        self.skills.values().collect()
    }

    /// Remove a skill by name. Returns `true` if it existed.
    pub fn remove(&mut self, name: &str) -> bool {
        self.skills.remove(name).is_some()
    }

    /// Find skills that contain the given tag.
    pub fn search(&self, tag: &str) -> Vec<&SkillDefinition> {
        self.skills
            .values()
            .filter(|s| s.tags.iter().any(|t| t == tag))
            .collect()
    }

    /// Number of registered skills.
    pub fn len(&self) -> usize {
        self.skills.len()
    }

    /// Returns true if the registry is empty.
    pub fn is_empty(&self) -> bool {
        self.skills.is_empty()
    }
}

// ---------------------------------------------------------------------------
// SkillExecutor
// ---------------------------------------------------------------------------

/// Validates and executes skills using a reference to the tool registry.
pub struct SkillExecutor<'a> {
    tool_registry: &'a ToolRegistry,
}

impl<'a> SkillExecutor<'a> {
    /// Create a new executor bound to the given tool registry.
    pub fn new(tool_registry: &'a ToolRegistry) -> Self {
        Self { tool_registry }
    }

    /// Validate a skill definition:
    /// - Every tool_name must exist in the tool registry.
    /// - Dependency indices must be in range.
    /// - The dependency graph must be acyclic.
    pub fn validate(&self, skill: &SkillDefinition) -> anyhow::Result<()> {
        let step_count = skill.steps.len();

        // Check tool existence and dependency indices.
        for (i, step) in skill.steps.iter().enumerate() {
            if self.tool_registry.get(&step.tool_name).is_none() {
                anyhow::bail!("step {} references unknown tool '{}'", i, step.tool_name);
            }
            for &dep in &step.depends_on {
                if dep >= step_count {
                    anyhow::bail!(
                        "step {} depends on index {} which is out of range (0..{})",
                        i,
                        dep,
                        step_count
                    );
                }
            }
        }

        // Cycle detection via topological sort.
        self.topological_sort(&skill.steps)?;

        Ok(())
    }

    /// Execute a skill's steps in dependency order, collecting results.
    pub async fn execute(&self, skill: &SkillDefinition) -> SkillExecution {
        let started_at = Utc::now();
        let mut step_results = Vec::new();
        let mut overall_success = true;

        let order = match self.topological_sort(&skill.steps) {
            Ok(o) => o,
            Err(_) => {
                return SkillExecution {
                    skill_name: skill.name.clone(),
                    started_at,
                    completed_at: Some(Utc::now()),
                    step_results,
                    overall_success: false,
                };
            }
        };

        for &idx in &order {
            let step = &skill.steps[idx];
            let step_start = std::time::Instant::now();

            let result = if let Some(tool) = self.tool_registry.get(&step.tool_name) {
                match tool.execute(step.arguments.clone()).await {
                    Ok(tr) => StepResult {
                        step_index: idx,
                        tool_name: step.tool_name.clone(),
                        success: tr.success,
                        output: tr.output,
                        duration_ms: step_start.elapsed().as_millis() as u64,
                    },
                    Err(e) => {
                        overall_success = false;
                        StepResult {
                            step_index: idx,
                            tool_name: step.tool_name.clone(),
                            success: false,
                            output: e.to_string(),
                            duration_ms: step_start.elapsed().as_millis() as u64,
                        }
                    }
                }
            } else {
                overall_success = false;
                StepResult {
                    step_index: idx,
                    tool_name: step.tool_name.clone(),
                    success: false,
                    output: format!("tool '{}' not found", step.tool_name),
                    duration_ms: step_start.elapsed().as_millis() as u64,
                }
            };

            if !result.success {
                overall_success = false;
            }

            step_results.push(result);
        }

        SkillExecution {
            skill_name: skill.name.clone(),
            started_at,
            completed_at: Some(Utc::now()),
            step_results,
            overall_success,
        }
    }

    /// Kahn's algorithm for topological sort. Returns ordered indices or
    /// an error if a cycle is detected.
    fn topological_sort(&self, steps: &[SkillStep]) -> anyhow::Result<Vec<usize>> {
        let n = steps.len();
        let mut in_degree = vec![0usize; n];
        let mut adj: Vec<Vec<usize>> = vec![Vec::new(); n];

        for (i, step) in steps.iter().enumerate() {
            for &dep in &step.depends_on {
                adj[dep].push(i);
                in_degree[i] += 1;
            }
        }

        let mut queue: std::collections::VecDeque<usize> = in_degree
            .iter()
            .enumerate()
            .filter(|(_, &d)| d == 0)
            .map(|(i, _)| i)
            .collect();

        let mut order = Vec::with_capacity(n);
        while let Some(node) = queue.pop_front() {
            order.push(node);
            for &next in &adj[node] {
                in_degree[next] -= 1;
                if in_degree[next] == 0 {
                    queue.push_back(next);
                }
            }
        }

        if order.len() != n {
            anyhow::bail!("dependency cycle detected in skill steps");
        }

        Ok(order)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tool::{EchoTool, ToolRegistry};

    fn sample_skill() -> SkillDefinition {
        SkillDefinition {
            name: "health-check".to_string(),
            description: "Run a basic health check".to_string(),
            version: "1.0.0".to_string(),
            author: "test".to_string(),
            steps: vec![
                SkillStep {
                    tool_name: "echo".to_string(),
                    arguments: serde_json::json!({"input": "ping"}),
                    description: "Send a ping".to_string(),
                    depends_on: vec![],
                },
                SkillStep {
                    tool_name: "echo".to_string(),
                    arguments: serde_json::json!({"input": "pong"}),
                    description: "Send a pong".to_string(),
                    depends_on: vec![0],
                },
            ],
            tags: vec!["health".to_string(), "diagnostic".to_string()],
            created_at: Utc::now(),
        }
    }

    fn tool_registry_with_echo() -> ToolRegistry {
        let mut reg = ToolRegistry::new();
        reg.register(Box::new(EchoTool));
        reg
    }

    #[test]
    fn register_and_get() {
        let mut registry = SkillRegistry::new();
        registry.register(sample_skill()).unwrap();
        let skill = registry.get("health-check");
        assert!(skill.is_some());
        assert_eq!(skill.unwrap().name, "health-check");
    }

    #[test]
    fn register_duplicate_errors() {
        let mut registry = SkillRegistry::new();
        registry.register(sample_skill()).unwrap();
        let result = registry.register(sample_skill());
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("already registered"));
    }

    #[test]
    fn list_skills() {
        let mut registry = SkillRegistry::new();
        registry.register(sample_skill()).unwrap();
        let list = registry.list();
        assert_eq!(list.len(), 1);
        assert_eq!(list[0].name, "health-check");
    }

    #[test]
    fn remove_skill() {
        let mut registry = SkillRegistry::new();
        registry.register(sample_skill()).unwrap();
        assert!(registry.remove("health-check"));
        assert!(registry.get("health-check").is_none());
        assert!(!registry.remove("health-check"));
    }

    #[test]
    fn search_by_tag() {
        let mut registry = SkillRegistry::new();
        registry.register(sample_skill()).unwrap();
        let found = registry.search("health");
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].name, "health-check");
    }

    #[test]
    fn search_no_match_returns_empty() {
        let mut registry = SkillRegistry::new();
        registry.register(sample_skill()).unwrap();
        let found = registry.search("nonexistent");
        assert!(found.is_empty());
    }

    #[test]
    fn validate_missing_tool_errors() {
        let tool_reg = ToolRegistry::new(); // empty — no tools
        let executor = SkillExecutor::new(&tool_reg);
        let result = executor.validate(&sample_skill());
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("unknown tool"));
    }

    #[test]
    fn validate_cycle_detection() {
        let tool_reg = tool_registry_with_echo();
        let executor = SkillExecutor::new(&tool_reg);

        let cyclic = SkillDefinition {
            name: "cyclic".to_string(),
            description: "bad".to_string(),
            version: "1.0.0".to_string(),
            author: "test".to_string(),
            steps: vec![
                SkillStep {
                    tool_name: "echo".to_string(),
                    arguments: serde_json::json!({}),
                    description: "A".to_string(),
                    depends_on: vec![1],
                },
                SkillStep {
                    tool_name: "echo".to_string(),
                    arguments: serde_json::json!({}),
                    description: "B".to_string(),
                    depends_on: vec![0],
                },
            ],
            tags: vec![],
            created_at: Utc::now(),
        };

        let result = executor.validate(&cyclic);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("cycle"));
    }

    #[test]
    fn validate_out_of_range_dependency() {
        let tool_reg = tool_registry_with_echo();
        let executor = SkillExecutor::new(&tool_reg);

        let bad = SkillDefinition {
            name: "bad-dep".to_string(),
            description: "bad".to_string(),
            version: "1.0.0".to_string(),
            author: "test".to_string(),
            steps: vec![SkillStep {
                tool_name: "echo".to_string(),
                arguments: serde_json::json!({}),
                description: "only step".to_string(),
                depends_on: vec![5],
            }],
            tags: vec![],
            created_at: Utc::now(),
        };

        let result = executor.validate(&bad);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("out of range"));
    }

    #[tokio::test]
    async fn execute_runs_steps_in_order() {
        let tool_reg = tool_registry_with_echo();
        let executor = SkillExecutor::new(&tool_reg);
        let skill = sample_skill();

        let execution = executor.execute(&skill).await;
        assert!(execution.overall_success);
        assert_eq!(execution.skill_name, "health-check");
        assert!(execution.completed_at.is_some());
        assert_eq!(execution.step_results.len(), 2);

        // Step 0 should execute before step 1.
        assert_eq!(execution.step_results[0].step_index, 0);
        assert_eq!(execution.step_results[0].output, "ping");
        assert_eq!(execution.step_results[1].step_index, 1);
        assert_eq!(execution.step_results[1].output, "pong");
    }

    #[test]
    fn skill_definition_serialization() {
        let skill = sample_skill();
        let json = serde_json::to_string(&skill).unwrap();
        let round: SkillDefinition = serde_json::from_str(&json).unwrap();
        assert_eq!(round.name, "health-check");
        assert_eq!(round.steps.len(), 2);
        assert_eq!(round.tags, vec!["health", "diagnostic"]);
    }

    #[test]
    fn empty_registry() {
        let registry = SkillRegistry::new();
        assert!(registry.is_empty());
        assert_eq!(registry.len(), 0);
        assert!(registry.list().is_empty());
        assert!(registry.get("anything").is_none());
    }
}

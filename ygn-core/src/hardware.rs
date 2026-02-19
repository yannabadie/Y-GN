//! Simulated hardware backend for embodiment.
//!
//! Provides the [`Hardware`] trait for interacting with physical actuators and
//! sensors, a [`SimulatedHardware`] implementation that tracks position/heading
//! in-memory, and a [`HardwareTool`] wrapper that exposes hardware actions as
//! an MCP-compatible [`Tool`].

use async_trait::async_trait;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::sync::Mutex;

use crate::tool::{Tool, ToolResult};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Direction for drive commands.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Direction {
    Forward,
    Backward,
    Left,
    Right,
    Stop,
}

/// Type of sensor to read.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SensorType {
    Temperature,
    Distance,
    Light,
    Pressure,
}

/// An action to perform on the hardware.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum HardwareAction {
    Drive { direction: Direction, speed: f64 },
    Sense { sensor_type: SensorType },
    Look { camera_id: String },
    Speak { text: String },
}

/// Result of executing a hardware action.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareResult {
    /// Description of the action that was executed.
    pub action: String,
    /// Whether the action succeeded.
    pub success: bool,
    /// Payload returned by the action.
    pub data: serde_json::Value,
    /// Timestamp when the result was produced.
    pub timestamp: String,
}

/// Snapshot of the simulated hardware state.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimState {
    pub x: f64,
    pub y: f64,
    pub heading: f64,
    pub speed: f64,
}

// ---------------------------------------------------------------------------
// Trait
// ---------------------------------------------------------------------------

/// Core trait for interacting with hardware (real or simulated).
#[async_trait]
pub trait Hardware: Send + Sync {
    /// Execute a hardware action.
    async fn execute(&self, action: HardwareAction) -> anyhow::Result<HardwareResult>;

    /// List capabilities this hardware provides.
    fn capabilities(&self) -> Vec<String>;

    /// Human-readable name for this hardware backend.
    fn name(&self) -> &str;
}

// ---------------------------------------------------------------------------
// SimulatedHardware
// ---------------------------------------------------------------------------

/// Internal mutable state for the simulated hardware.
#[derive(Debug)]
struct SimInner {
    x: f64,
    y: f64,
    heading: f64,
    speed: f64,
    seed: u64,
}

/// A simulated hardware backend that tracks position, heading, and speed
/// in-memory.  Sensor readings are deterministic given the seed.
#[derive(Debug)]
pub struct SimulatedHardware {
    inner: Mutex<SimInner>,
}

impl Default for SimulatedHardware {
    fn default() -> Self {
        Self::new(42)
    }
}

impl SimulatedHardware {
    /// Create a new simulated hardware with the given RNG seed.
    pub fn new(seed: u64) -> Self {
        Self {
            inner: Mutex::new(SimInner {
                x: 0.0,
                y: 0.0,
                heading: 0.0,
                speed: 0.0,
                seed,
            }),
        }
    }

    /// Get a snapshot of the current simulated state.
    pub fn state(&self) -> SimState {
        let inner = self.inner.lock().unwrap();
        SimState {
            x: inner.x,
            y: inner.y,
            heading: inner.heading,
            speed: inner.speed,
        }
    }

    /// Simple deterministic pseudo-random number in [0, 1) using the seed.
    fn next_rand(inner: &mut SimInner) -> f64 {
        // Simple xorshift-style PRNG for deterministic simulation.
        inner.seed ^= inner.seed << 13;
        inner.seed ^= inner.seed >> 7;
        inner.seed ^= inner.seed << 17;
        (inner.seed % 10000) as f64 / 10000.0
    }
}

#[async_trait]
impl Hardware for SimulatedHardware {
    async fn execute(&self, action: HardwareAction) -> anyhow::Result<HardwareResult> {
        let mut inner = self.inner.lock().map_err(|e| anyhow::anyhow!("{e}"))?;

        let timestamp = Utc::now().to_rfc3339();

        match action {
            HardwareAction::Drive { direction, speed } => {
                inner.speed = speed;
                match direction {
                    Direction::Forward => {
                        let rad = inner.heading.to_radians();
                        inner.x += speed * rad.cos();
                        inner.y += speed * rad.sin();
                    }
                    Direction::Backward => {
                        let rad = inner.heading.to_radians();
                        inner.x -= speed * rad.cos();
                        inner.y -= speed * rad.sin();
                    }
                    Direction::Left => {
                        inner.heading = (inner.heading - 90.0) % 360.0;
                        if inner.heading < 0.0 {
                            inner.heading += 360.0;
                        }
                    }
                    Direction::Right => {
                        inner.heading = (inner.heading + 90.0) % 360.0;
                    }
                    Direction::Stop => {
                        inner.speed = 0.0;
                    }
                }
                Ok(HardwareResult {
                    action: format!("drive:{direction:?}"),
                    success: true,
                    data: serde_json::json!({
                        "x": inner.x,
                        "y": inner.y,
                        "heading": inner.heading,
                        "speed": inner.speed,
                    }),
                    timestamp,
                })
            }
            HardwareAction::Sense { sensor_type } => {
                let rand_val = Self::next_rand(&mut inner);
                let (value, unit) = match sensor_type {
                    SensorType::Temperature => {
                        // Range: -20.0 to 50.0 Celsius
                        let temp = -20.0 + rand_val * 70.0;
                        (temp, "celsius")
                    }
                    SensorType::Distance => {
                        // Range: 0.0 to 1000.0 cm
                        let dist = rand_val * 1000.0;
                        (dist, "cm")
                    }
                    SensorType::Light => {
                        // Range: 0.0 to 100000.0 lux
                        let lux = rand_val * 100000.0;
                        (lux, "lux")
                    }
                    SensorType::Pressure => {
                        // Range: 950.0 to 1050.0 hPa
                        let p = 950.0 + rand_val * 100.0;
                        (p, "hPa")
                    }
                };
                Ok(HardwareResult {
                    action: format!("sense:{sensor_type:?}"),
                    success: true,
                    data: serde_json::json!({
                        "value": value,
                        "unit": unit,
                    }),
                    timestamp,
                })
            }
            HardwareAction::Look { camera_id } => Ok(HardwareResult {
                action: format!("look:{camera_id}"),
                success: true,
                data: serde_json::json!({
                    "description": format!(
                        "Simulated image from camera '{camera_id}': \
                         a room with dim lighting and a desk in the center"
                    ),
                }),
                timestamp,
            }),
            HardwareAction::Speak { text } => Ok(HardwareResult {
                action: "speak".to_string(),
                success: true,
                data: serde_json::json!({
                    "spoken_text": text,
                    "duration_ms": text.len() * 80,
                }),
                timestamp,
            }),
        }
    }

    fn capabilities(&self) -> Vec<String> {
        vec![
            "drive".to_string(),
            "sense".to_string(),
            "look".to_string(),
            "speak".to_string(),
        ]
    }

    fn name(&self) -> &str {
        "simulated_hardware"
    }
}

// ---------------------------------------------------------------------------
// HardwareTool — wraps SimulatedHardware as a Tool
// ---------------------------------------------------------------------------

/// Wraps [`SimulatedHardware`] so it can be called through the MCP tool
/// interface like any other tool.
pub struct HardwareTool {
    hw: SimulatedHardware,
}

impl std::fmt::Debug for HardwareTool {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("HardwareTool")
            .field("name", &"hardware")
            .finish()
    }
}

impl Default for HardwareTool {
    fn default() -> Self {
        Self::new()
    }
}

impl HardwareTool {
    /// Create a new HardwareTool with default simulated hardware.
    pub fn new() -> Self {
        Self {
            hw: SimulatedHardware::default(),
        }
    }

    /// Create a HardwareTool with a specific seed.
    pub fn with_seed(seed: u64) -> Self {
        Self {
            hw: SimulatedHardware::new(seed),
        }
    }
}

#[async_trait]
impl Tool for HardwareTool {
    fn name(&self) -> &str {
        "hardware"
    }

    fn description(&self) -> &str {
        "Execute hardware actions (drive, sense, look, speak) on simulated hardware"
    }

    fn parameters_schema(&self) -> serde_json::Value {
        serde_json::json!({
            "type": "object",
            "properties": {
                "action": {
                    "type": "object",
                    "description": "Hardware action to execute",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["drive", "sense", "look", "speak"],
                            "description": "The type of hardware action"
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["forward", "backward", "left", "right", "stop"],
                            "description": "Direction for drive actions"
                        },
                        "speed": {
                            "type": "number",
                            "description": "Speed for drive actions"
                        },
                        "sensor_type": {
                            "type": "string",
                            "enum": ["temperature", "distance", "light", "pressure"],
                            "description": "Sensor type for sense actions"
                        },
                        "camera_id": {
                            "type": "string",
                            "description": "Camera identifier for look actions"
                        },
                        "text": {
                            "type": "string",
                            "description": "Text for speak actions"
                        }
                    },
                    "required": ["type"]
                }
            },
            "required": ["action"]
        })
    }

    async fn execute(&self, args: serde_json::Value) -> anyhow::Result<ToolResult> {
        let action_val = args
            .get("action")
            .ok_or_else(|| anyhow::anyhow!("Missing required parameter: action"))?;

        let action: HardwareAction = serde_json::from_value(action_val.clone())
            .map_err(|e| anyhow::anyhow!("Invalid action: {e}"))?;

        match self.hw.execute(action).await {
            Ok(result) => Ok(ToolResult {
                success: result.success,
                output: serde_json::to_string(&result)?,
                error: None,
            }),
            Err(e) => Ok(ToolResult {
                success: false,
                output: String::new(),
                error: Some(e.to_string()),
            }),
        }
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn drive_forward_changes_position() {
        let hw = SimulatedHardware::new(1);
        // Heading is 0 (east-facing), drive forward at speed 10.
        hw.execute(HardwareAction::Drive {
            direction: Direction::Forward,
            speed: 10.0,
        })
        .await
        .unwrap();

        let state = hw.state();
        // cos(0) = 1, sin(0) = 0 → x increases, y stays ~0
        assert!((state.x - 10.0).abs() < 0.001);
        assert!(state.y.abs() < 0.001);
    }

    #[tokio::test]
    async fn drive_backward_changes_position() {
        let hw = SimulatedHardware::new(1);
        hw.execute(HardwareAction::Drive {
            direction: Direction::Backward,
            speed: 5.0,
        })
        .await
        .unwrap();

        let state = hw.state();
        assert!((state.x - (-5.0)).abs() < 0.001);
    }

    #[tokio::test]
    async fn drive_left_right_changes_heading() {
        let hw = SimulatedHardware::new(1);

        // Turn right
        hw.execute(HardwareAction::Drive {
            direction: Direction::Right,
            speed: 0.0,
        })
        .await
        .unwrap();
        let state = hw.state();
        assert!((state.heading - 90.0).abs() < 0.001);

        // Turn left
        hw.execute(HardwareAction::Drive {
            direction: Direction::Left,
            speed: 0.0,
        })
        .await
        .unwrap();
        let state = hw.state();
        assert!(state.heading.abs() < 0.001);
    }

    #[tokio::test]
    async fn sense_temperature_returns_valid_range() {
        let hw = SimulatedHardware::new(42);
        let result = hw
            .execute(HardwareAction::Sense {
                sensor_type: SensorType::Temperature,
            })
            .await
            .unwrap();

        assert!(result.success);
        let value = result.data["value"].as_f64().unwrap();
        assert!((-20.0..=50.0).contains(&value));
        assert_eq!(result.data["unit"], "celsius");
    }

    #[tokio::test]
    async fn sense_distance_returns_valid_range() {
        let hw = SimulatedHardware::new(42);
        let result = hw
            .execute(HardwareAction::Sense {
                sensor_type: SensorType::Distance,
            })
            .await
            .unwrap();

        assert!(result.success);
        let value = result.data["value"].as_f64().unwrap();
        assert!((0.0..=1000.0).contains(&value));
        assert_eq!(result.data["unit"], "cm");
    }

    #[tokio::test]
    async fn look_returns_description() {
        let hw = SimulatedHardware::new(1);
        let result = hw
            .execute(HardwareAction::Look {
                camera_id: "front".to_string(),
            })
            .await
            .unwrap();

        assert!(result.success);
        let desc = result.data["description"].as_str().unwrap();
        assert!(desc.contains("front"));
        assert!(desc.contains("Simulated image"));
    }

    #[tokio::test]
    async fn speak_returns_success() {
        let hw = SimulatedHardware::new(1);
        let result = hw
            .execute(HardwareAction::Speak {
                text: "Hello world".to_string(),
            })
            .await
            .unwrap();

        assert!(result.success);
        assert_eq!(result.data["spoken_text"], "Hello world");
        assert!(result.data["duration_ms"].as_u64().unwrap() > 0);
    }

    #[tokio::test]
    async fn hardware_tool_execute_via_json() {
        let tool = HardwareTool::with_seed(42);
        let args = serde_json::json!({
            "action": {
                "type": "drive",
                "direction": "forward",
                "speed": 5.0
            }
        });

        let result = tool.execute(args).await.unwrap();
        assert!(result.success);
        assert!(result.error.is_none());

        // Parse the output to verify it contains position data.
        let hw_result: HardwareResult = serde_json::from_str(&result.output).unwrap();
        assert!(hw_result.success);
        assert!(hw_result.data["x"].as_f64().unwrap() > 0.0);
    }

    #[tokio::test]
    async fn hardware_tool_speak_via_json() {
        let tool = HardwareTool::with_seed(1);
        let args = serde_json::json!({
            "action": {
                "type": "speak",
                "text": "test message"
            }
        });

        let result = tool.execute(args).await.unwrap();
        assert!(result.success);
        let hw_result: HardwareResult = serde_json::from_str(&result.output).unwrap();
        assert_eq!(hw_result.data["spoken_text"], "test message");
    }

    #[tokio::test]
    async fn hardware_tool_missing_action_errors() {
        let tool = HardwareTool::new();
        let args = serde_json::json!({});
        let result = tool.execute(args).await;
        assert!(result.is_err());
    }

    #[test]
    fn hardware_tool_spec() {
        let tool = HardwareTool::new();
        let spec = tool.spec();
        assert_eq!(spec.name, "hardware");
        assert!(!spec.description.is_empty());
        assert!(spec.parameters_schema["properties"]["action"].is_object());
    }

    #[test]
    fn drive_stop_zeroes_speed() {
        let hw = SimulatedHardware::new(1);
        let rt = tokio::runtime::Runtime::new().unwrap();
        rt.block_on(async {
            hw.execute(HardwareAction::Drive {
                direction: Direction::Forward,
                speed: 10.0,
            })
            .await
            .unwrap();
            assert!((hw.state().speed - 10.0).abs() < 0.001);

            hw.execute(HardwareAction::Drive {
                direction: Direction::Stop,
                speed: 10.0,
            })
            .await
            .unwrap();
            assert!(hw.state().speed.abs() < 0.001);
        });
    }

    #[test]
    fn sim_state_serialization() {
        let state = SimState {
            x: 1.0,
            y: 2.0,
            heading: 90.0,
            speed: 5.0,
        };
        let json = serde_json::to_string(&state).unwrap();
        let round: SimState = serde_json::from_str(&json).unwrap();
        assert!((round.x - 1.0).abs() < 0.001);
        assert!((round.heading - 90.0).abs() < 0.001);
    }
}

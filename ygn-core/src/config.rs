use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeConfig {
    pub node_role: String,
    pub trust_tier: String,
    pub gateway_bind: String,
}

impl Default for NodeConfig {
    fn default() -> Self {
        Self {
            node_role: "edge".to_string(),
            trust_tier: "trusted".to_string(),
            gateway_bind: "0.0.0.0:3000".to_string(),
        }
    }
}

impl NodeConfig {
    pub fn load_or_default() -> Self {
        // TODO: load from file/env
        Self::default()
    }

    pub fn json_schema() -> String {
        serde_json::to_string_pretty(&serde_json::json!({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "YGN Node Configuration",
            "type": "object",
            "properties": {
                "node_role": {
                    "type": "string",
                    "enum": ["edge", "core", "brain-proxy"],
                    "default": "edge"
                },
                "trust_tier": {
                    "type": "string",
                    "enum": ["trusted", "untrusted"],
                    "default": "trusted"
                },
                "gateway_bind": {
                    "type": "string",
                    "default": "0.0.0.0:3000"
                }
            }
        }))
        .unwrap()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_config_is_valid() {
        let cfg = NodeConfig::default();
        assert_eq!(cfg.node_role, "edge");
        assert_eq!(cfg.trust_tier, "trusted");
    }

    #[test]
    fn json_schema_is_valid_json() {
        let schema = NodeConfig::json_schema();
        let parsed: serde_json::Value = serde_json::from_str(&schema).unwrap();
        assert_eq!(parsed["title"], "YGN Node Configuration");
    }
}

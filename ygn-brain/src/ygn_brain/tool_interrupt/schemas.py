"""Schema registry for per-tool output JSON Schemas."""

from __future__ import annotations

from typing import Any


class SchemaRegistry:
    """Registry of per-tool output JSON Schemas."""

    def __init__(self) -> None:
        self._schemas: dict[str, dict[str, Any]] = {}

    def register(self, tool_name: str, schema: dict[str, Any]) -> None:
        self._schemas[tool_name] = schema

    def get(self, tool_name: str) -> dict[str, Any] | None:
        return self._schemas.get(tool_name)

    def validate(self, tool_name: str, data: Any) -> tuple[bool, list[str]]:
        """Validate data against tool's schema. Returns (valid, errors)."""
        schema = self._schemas.get(tool_name)
        if schema is None:
            return True, []

        errors: list[str] = []
        expected_type = schema.get("type")
        if expected_type == "object" and not isinstance(data, dict):
            errors.append(f"Expected object, got {type(data).__name__}")
            return False, errors

        if expected_type == "object" and isinstance(data, dict):
            for field in schema.get("required", []):
                if field not in data:
                    errors.append(f"Missing required field: {field}")

            props = schema.get("properties", {})
            for key, val in data.items():
                if key in props:
                    prop_type = props[key].get("type")
                    if prop_type == "string" and not isinstance(val, str):
                        errors.append(f"Field '{key}': expected string, got {type(val).__name__}")
                    elif prop_type == "number" and not isinstance(val, (int, float)):
                        errors.append(f"Field '{key}': expected number, got {type(val).__name__}")
                    elif prop_type == "boolean" and not isinstance(val, bool):
                        errors.append(f"Field '{key}': expected boolean, got {type(val).__name__}")

        return len(errors) == 0, errors

    def auto_discover(self, tools: list[dict[str, Any]]) -> None:
        """Import output schemas from MCP tools/list response."""
        for tool in tools:
            name = tool.get("name", "")
            output_schema = tool.get("outputSchema")
            if name and output_schema:
                self._schemas[name] = output_schema

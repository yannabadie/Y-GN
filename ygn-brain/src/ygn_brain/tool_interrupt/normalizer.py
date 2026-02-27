"""PerceptionAligner — normalizes raw tool outputs for LLM consumption."""

from __future__ import annotations

import json
import re
from typing import Any

from .schemas import SchemaRegistry

_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{8,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}"), "[REDACTED_BEARER]"),
    (re.compile(r"(?i)password\s*[=:]\s*\S+"), "[REDACTED_PASSWORD]"),
    (re.compile(r"(?i)api[_-]?key\s*[=:]\s*\S+"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?i)secret\s*[=:]\s*\S+"), "[REDACTED_SECRET]"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"gho_[A-Za-z0-9]{36}"), "[REDACTED_GH_TOKEN]"),
]


def _redact(text: str) -> tuple[str, list[str]]:
    """Redact secrets from text. Returns (redacted_text, list of redacted field names)."""
    redacted_fields: list[str] = []
    result = text
    for pattern, replacement in _SECRET_PATTERNS:
        if pattern.search(result):
            redacted_fields.append(replacement)
            result = pattern.sub(replacement, result)
    return result, redacted_fields


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated + "..."


class PerceptionAligner:
    """Normalizes raw tool outputs: schema validation + redaction + summaries."""

    def __init__(self, schema_registry: SchemaRegistry) -> None:
        self._registry = schema_registry

    def normalize(self, tool_name: str, raw_output: str) -> dict[str, Any]:
        """Normalize a raw tool output string."""
        parsed: Any = None
        is_json = False
        try:
            parsed = json.loads(raw_output)
            is_json = True
        except (json.JSONDecodeError, TypeError):
            parsed = raw_output

        validation_errors: list[str] = []
        valid = True
        if is_json:
            valid, validation_errors = self._registry.validate(tool_name, parsed)

        redacted_text, redacted_fields = _redact(
            json.dumps(parsed) if is_json else str(parsed)
        )

        summary_concise = _truncate(redacted_text, 200)
        summary_detailed = _truncate(redacted_text, 2000)

        return {
            "valid": valid,
            "data": parsed,
            "summary_concise": summary_concise,
            "summary_detailed": summary_detailed,
            "redacted_fields": redacted_fields,
            "validation_errors": validation_errors,
        }

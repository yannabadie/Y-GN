"""Tests for PerceptionAligner and SchemaRegistry."""

from ygn_brain.tool_interrupt.normalizer import PerceptionAligner
from ygn_brain.tool_interrupt.schemas import SchemaRegistry


def test_schema_registry_register_and_validate():
    reg = SchemaRegistry()
    reg.register("echo", {
        "type": "object",
        "properties": {"output": {"type": "string"}},
        "required": ["output"],
    })
    valid, errors = reg.validate("echo", {"output": "hello"})
    assert valid
    assert not errors

    valid2, errors2 = reg.validate("echo", {"wrong_field": 123})
    assert not valid2
    assert len(errors2) > 0


def test_schema_registry_unregistered_tool():
    reg = SchemaRegistry()
    valid, errors = reg.validate("unknown_tool", {"any": "data"})
    # Unregistered tools pass validation (no schema to check against)
    assert valid
    assert not errors


def test_normalizer_redacts_secrets():
    reg = SchemaRegistry()
    aligner = PerceptionAligner(schema_registry=reg)

    raw = '{"output": "result", "api_key": "sk-abc123xyz", "token": "Bearer eyJhbGciOiJ"}'
    result = aligner.normalize("some_tool", raw)
    assert result["valid"]
    assert "sk-abc123xyz" not in result["summary_concise"]
    assert "sk-abc123xyz" not in result["summary_detailed"]
    assert len(result["redacted_fields"]) > 0


def test_normalizer_generates_summaries():
    reg = SchemaRegistry()
    aligner = PerceptionAligner(schema_registry=reg)

    raw = "x" * 5000
    result = aligner.normalize("big_tool", raw)
    assert len(result["summary_concise"]) <= 220
    assert len(result["summary_detailed"]) <= 2020
    assert result["valid"]


def test_normalizer_validates_against_schema():
    reg = SchemaRegistry()
    reg.register("calc", {
        "type": "object",
        "properties": {"result": {"type": "number"}},
        "required": ["result"],
    })
    aligner = PerceptionAligner(schema_registry=reg)

    # Valid JSON matching schema
    result = aligner.normalize("calc", '{"result": 42}')
    assert result["valid"]

    # Valid JSON NOT matching schema
    result2 = aligner.normalize("calc", '{"wrong": "field"}')
    assert not result2["valid"]
    assert len(result2["validation_errors"]) > 0

"""Tests for entity extraction."""

import pytest

from ygn_brain.entity_extraction import (
    EntityExtractor,
    RegexEntityExtractor,
    StubEntityExtractor,
)


def test_entity_extractor_is_abstract():
    with pytest.raises(TypeError):
        EntityExtractor()  # type: ignore[abstract]


def test_stub_returns_empty():
    ext = StubEntityExtractor()
    assert ext.extract("hello world") == []


def test_regex_extracts_functions():
    ext = RegexEntityExtractor()
    entities = ext.extract("Call def process_data and class DataHandler")
    assert "process_data" in entities
    assert "DataHandler" in entities


def test_regex_extracts_urls():
    ext = RegexEntityExtractor()
    entities = ext.extract("Visit https://api.example.com/v1/users")
    assert any("api.example.com" in e for e in entities)


def test_regex_extracts_file_paths():
    ext = RegexEntityExtractor()
    entities = ext.extract("Edit /src/main.py and /config/settings.toml")
    assert any("main.py" in e for e in entities)


def test_regex_empty_input():
    ext = RegexEntityExtractor()
    assert ext.extract("") == []


def test_regex_no_entities():
    ext = RegexEntityExtractor()
    assert ext.extract("The weather is nice today") == []

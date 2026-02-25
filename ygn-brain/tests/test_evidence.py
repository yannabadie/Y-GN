"""Tests for Evidence Pack module."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ygn_brain.evidence import EvidenceEntry, EvidenceKind, EvidencePack


def test_evidence_pack_creation():
    pack = EvidencePack(session_id="test123")
    assert pack.session_id == "test123"
    assert len(pack.entries) == 0


def test_evidence_pack_add_and_jsonl():
    pack = EvidencePack(session_id="test456")
    pack.add("diagnosis", "input", {"query": "hello"})
    pack.add("analysis", "decision", {"strategy": "direct"})

    jsonl = pack.to_jsonl()
    lines = jsonl.strip().split("\n")
    assert len(lines) == 2

    entry = json.loads(lines[0])
    assert entry["phase"] == "diagnosis"
    assert entry["kind"] == "input"


def test_evidence_pack_save(tmp_path: Path):
    pack = EvidencePack(session_id="save_test")
    pack.add("execution", "output", {"result": "ok"})
    path = pack.save(tmp_path)
    assert path.exists()
    content = path.read_text()
    assert "save_test" not in content  # session_id is in filename, not entries
    assert "execution" in content


# ---------------------------------------------------------------------------
# Fix 2.3: EvidenceKind constrains valid kinds
# ---------------------------------------------------------------------------


def test_evidence_kind_enum_values():
    """Fix 2.3: EvidenceKind constrains valid kinds."""
    assert set(EvidenceKind) == {"input", "decision", "tool_call", "source", "output", "error"}


def test_evidence_kind_valid():
    """Fix 2.3: valid kinds create entries successfully."""
    for kind in EvidenceKind:
        entry = EvidenceEntry(phase="test", kind=kind, data={})
        assert entry.kind == kind


def test_evidence_kind_invalid_raises():
    """Fix 2.3: invalid kind raises ValidationError."""
    with pytest.raises(ValidationError):
        EvidenceEntry(phase="test", kind="invalid_kind", data={})


def test_evidence_pack_add_invalid_kind_raises():
    """Fix 2.3: adding invalid kind via pack raises ValueError."""
    pack = EvidencePack(session_id="kind_test")
    with pytest.raises(ValueError, match="bogus_kind"):
        pack.add("test", "bogus_kind", {})


def test_evidence_jsonl_seven_phases():
    """Phase 4.2: 7-phase pipeline produces valid JSONL with all expected entries."""
    pack = EvidencePack(session_id="jsonl_test")
    phases = [
        "diagnosis", "analysis", "planning", "execution",
        "validation", "synthesis", "complete",
    ]
    kinds = ["input", "decision", "decision", "output", "decision", "output", "output"]
    for phase, kind in zip(phases, kinds, strict=True):
        pack.add(phase, kind, {"phase": phase})

    jsonl = pack.to_jsonl()
    lines = jsonl.strip().split("\n")
    assert len(lines) == 7

    for line in lines:
        parsed = json.loads(line)
        assert "phase" in parsed
        assert "kind" in parsed
        assert "timestamp" in parsed
        assert "data" in parsed
        # Verify kind is a valid EvidenceKind value
        assert parsed["kind"] in set(EvidenceKind)

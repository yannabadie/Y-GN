"""Tests for Evidence Pack module."""

import json
from pathlib import Path

from ygn_brain.evidence import EvidencePack


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

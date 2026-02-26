"""Tests for Evidence Pack module."""

import json
import time
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
        "diagnosis",
        "analysis",
        "planning",
        "execution",
        "validation",
        "synthesis",
        "complete",
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


# ---------------------------------------------------------------------------
# v0.3.0 Phase 1: Evidence Pack Crypto (A1)
# ---------------------------------------------------------------------------


def test_hash_chain_integrity():
    """7 entries: each prev_hash links to prior entry_hash."""
    pack = EvidencePack(session_id="chain_test")
    phases = [
        "diagnosis",
        "analysis",
        "planning",
        "execution",
        "validation",
        "synthesis",
        "complete",
    ]
    for phase in phases:
        pack.add(phase, "decision", {"phase": phase})

    assert len(pack.entries) == 7
    assert pack.entries[0].prev_hash == ""
    for i in range(1, 7):
        assert pack.entries[i].prev_hash == pack.entries[i - 1].entry_hash
        assert pack.entries[i].prev_hash != ""
    assert pack.verify()


def test_hash_chain_tamper_detection():
    """Modifying an entry's data makes verify() return False."""
    pack = EvidencePack(session_id="tamper_test")
    pack.add("phase1", "input", {"secret": "original"})
    pack.add("phase2", "decision", {"choice": "A"})
    pack.add("phase3", "output", {"result": "ok"})

    assert pack.verify() is True
    # Tamper with the second entry's data
    pack.entries[1].data = {"choice": "TAMPERED"}
    assert pack.verify() is False


def test_ed25519_sign_and_verify():
    """Sign pack with ed25519, verify succeeds."""
    from nacl.signing import SigningKey

    pack = EvidencePack(session_id="sign_test")
    pack.add("phase1", "input", {"x": 1})
    pack.add("phase2", "output", {"y": 2})

    sk = SigningKey.generate()
    private_key_hex = sk.encode().hex()

    pack.sign(private_key_hex)
    assert pack.signer_public_key != ""
    assert all(e.signature != "" for e in pack.entries)
    assert pack.verify() is True


def test_ed25519_wrong_key_fails():
    """Sign with key A, verify with key B's public key fails."""
    from nacl.signing import SigningKey

    pack = EvidencePack(session_id="wrongkey_test")
    pack.add("phase1", "input", {"x": 1})

    sk_a = SigningKey.generate()
    sk_b = SigningKey.generate()

    pack.sign(sk_a.encode().hex())
    assert pack.verify(sk_b.verify_key.encode().hex()) is False


def test_merkle_root_deterministic():
    """Same entries produce the same merkle root."""
    pack = EvidencePack(session_id="merkle_test")
    pack.add("phase1", "input", {"x": 1})
    pack.add("phase2", "output", {"y": 2})

    root1 = pack.merkle_root_hash()
    root2 = pack.merkle_root_hash()
    assert root1 == root2
    assert len(root1) == 64  # SHA-256 hex digest


def test_eu_ai_act_fields():
    """start_time, end_time, model_id populated after pipeline run."""
    pack = EvidencePack(session_id="eu_test", model_id="gemini-2.5-flash")
    pack.add("diagnosis", "input", {"query": "test"})
    pack.add("synthesis", "output", {"result": "done"})

    assert pack.start_time > 0
    assert pack.end_time >= pack.start_time
    assert pack.model_id == "gemini-2.5-flash"


def test_unsigned_pack_still_works():
    """Backward compat: verify() on unsigned pack returns True (chain-only)."""
    pack = EvidencePack(session_id="unsigned_test")
    pack.add("phase1", "input", {"x": 1})
    pack.add("phase2", "output", {"y": 2})
    # No sign() call — should still verify via hash chain only
    assert pack.verify() is True
    assert pack.signer_public_key == ""
    assert all(e.signature == "" for e in pack.entries)


def test_entry_id_time_sortable():
    """Entry IDs are lexicographically ordered by creation time."""
    pack = EvidencePack(session_id="sort_test")
    for i in range(5):
        pack.add("phase", "input", {"i": i})
        time.sleep(0.015)  # 15ms gap ensures different millisecond prefixes

    ids = [e.entry_id for e in pack.entries]
    assert ids == sorted(ids)

"""Tests for evolution loop — scaffold self-modification with safety gates."""

from __future__ import annotations

import os
import tempfile

import pytest

from ygn_brain.evolution import (
    EvolutionEngine,
    EvolutionProposal,
    EvolutionScope,
    FileWhitelist,
    SafetyGuard,
)

# ---------------------------------------------------------------------------
# FileWhitelist
# ---------------------------------------------------------------------------


def test_whitelist_allows_toml_files() -> None:
    wl = FileWhitelist()
    assert wl.is_allowed("pyproject.toml") is True
    assert wl.is_allowed("settings.toml") is True


def test_whitelist_blocks_source_py_files() -> None:
    wl = FileWhitelist()
    assert wl.is_allowed("src/ygn_brain/evolution.py") is False
    assert wl.is_allowed("main.py") is False


def test_whitelist_allows_test_py_files() -> None:
    wl = FileWhitelist()
    assert wl.is_allowed("tests/test_evolution.py") is True
    assert wl.is_allowed("tests/sub/test_deep.py") is True


# ---------------------------------------------------------------------------
# EvolutionEngine.propose
# ---------------------------------------------------------------------------


def test_propose_creates_valid_proposal() -> None:
    engine = EvolutionEngine()
    proposal = engine.propose(
        scope=EvolutionScope.CONFIG,
        target_file="config.toml",
        description="Update timeout",
        proposed_content="timeout = 60",
    )
    assert proposal.scope == EvolutionScope.CONFIG
    assert proposal.target_file == "config.toml"
    assert proposal.description == "Update timeout"
    assert proposal.proposed_content == "timeout = 60"
    assert len(proposal.proposal_id) > 0


def test_propose_rejects_file_not_in_whitelist() -> None:
    engine = EvolutionEngine()
    with pytest.raises(ValueError, match="not in whitelist"):
        engine.propose(
            scope=EvolutionScope.CONFIG,
            target_file="src/ygn_brain/core.py",
            description="Hack core",
            proposed_content="evil()",
        )


# ---------------------------------------------------------------------------
# EvolutionEngine.validate
# ---------------------------------------------------------------------------


def test_validate_detects_empty_content() -> None:
    engine = EvolutionEngine()
    proposal = EvolutionProposal(
        proposal_id="test-id",
        scope=EvolutionScope.CONFIG,
        description="empty change",
        target_file="config.toml",
        original_content="key = 1",
        proposed_content="   ",
        created_at=0.0,
        confidence=1.0,
    )
    results = engine.validate(proposal)
    non_empty_gate = next(r for r in results if r.gate_name == "non_empty")
    assert non_empty_gate.passed is False


def test_validate_detects_no_diff() -> None:
    engine = EvolutionEngine()
    proposal = EvolutionProposal(
        proposal_id="test-id",
        scope=EvolutionScope.CONFIG,
        description="no-op change",
        target_file="config.toml",
        original_content="key = 1",
        proposed_content="key = 1",
        created_at=0.0,
        confidence=1.0,
    )
    results = engine.validate(proposal)
    diff_gate = next(r for r in results if r.gate_name == "diff_exists")
    assert diff_gate.passed is False


# ---------------------------------------------------------------------------
# EvolutionEngine.apply
# ---------------------------------------------------------------------------


def test_apply_in_dry_run_returns_not_applied() -> None:
    engine = EvolutionEngine(dry_run=True)
    proposal = EvolutionProposal(
        proposal_id="test-id",
        scope=EvolutionScope.CONFIG,
        description="update config",
        target_file="config.toml",
        original_content="key = 1",
        proposed_content="key = 2",
        created_at=0.0,
        confidence=1.0,
    )
    result = engine.apply(proposal)
    assert result.applied is False
    assert "dry run" in result.reason.lower()


# ---------------------------------------------------------------------------
# EvolutionEngine.generate_diff
# ---------------------------------------------------------------------------


def test_generate_diff_produces_unified_diff() -> None:
    engine = EvolutionEngine()
    proposal = EvolutionProposal(
        proposal_id="diff-test",
        scope=EvolutionScope.CONFIG,
        description="change value",
        target_file="config.toml",
        original_content="key = 1\n",
        proposed_content="key = 2\n",
        created_at=0.0,
        confidence=1.0,
    )
    diff = engine.generate_diff(proposal)
    assert "---" in diff
    assert "+++" in diff
    assert "-key = 1" in diff
    assert "+key = 2" in diff


# ---------------------------------------------------------------------------
# SafetyGuard
# ---------------------------------------------------------------------------


def test_safety_guard_blocks_eval() -> None:
    guard = SafetyGuard()
    proposal = EvolutionProposal(
        proposal_id="evil-1",
        scope=EvolutionScope.CONFIG,
        description="inject eval",
        target_file="config.toml",
        original_content="",
        proposed_content='value = eval("1+1")',
        created_at=0.0,
        confidence=0.9,
    )
    safe, reason = guard.check_proposal(proposal)
    assert safe is False
    assert "eval" in reason.lower()


def test_safety_guard_blocks_rm_rf() -> None:
    guard = SafetyGuard()
    proposal = EvolutionProposal(
        proposal_id="evil-2",
        scope=EvolutionScope.CONFIG,
        description="inject rm",
        target_file="config.toml",
        original_content="",
        proposed_content="cleanup = rm -rf /",
        created_at=0.0,
        confidence=0.9,
    )
    safe, reason = guard.check_proposal(proposal)
    assert safe is False
    assert "rm" in reason.lower()


def test_safety_guard_blocks_low_confidence() -> None:
    guard = SafetyGuard()
    proposal = EvolutionProposal(
        proposal_id="low-conf",
        scope=EvolutionScope.CONFIG,
        description="uncertain change",
        target_file="config.toml",
        original_content="key = 1",
        proposed_content="key = 2",
        created_at=0.0,
        confidence=0.1,
    )
    safe, reason = guard.check_proposal(proposal)
    assert safe is False
    assert "confidence" in reason.lower()


def test_safety_guard_allows_safe_changes() -> None:
    guard = SafetyGuard()
    proposal = EvolutionProposal(
        proposal_id="safe-1",
        scope=EvolutionScope.CONFIG,
        description="bump timeout",
        target_file="config.toml",
        original_content="timeout = 30",
        proposed_content="timeout = 60",
        created_at=0.0,
        confidence=0.9,
    )
    safe, reason = guard.check_proposal(proposal)
    assert safe is True
    assert "passed" in reason.lower()


# ---------------------------------------------------------------------------
# History tracking
# ---------------------------------------------------------------------------


def test_evolution_history_tracks_results() -> None:
    engine = EvolutionEngine(dry_run=True)
    assert len(engine.history) == 0

    proposal = EvolutionProposal(
        proposal_id="hist-1",
        scope=EvolutionScope.CONFIG,
        description="change a",
        target_file="config.toml",
        original_content="a = 1",
        proposed_content="a = 2",
        created_at=0.0,
        confidence=1.0,
    )
    engine.apply(proposal)
    assert len(engine.history) == 1
    assert engine.history[0].proposal_id == "hist-1"

    proposal2 = EvolutionProposal(
        proposal_id="hist-2",
        scope=EvolutionScope.TEST,
        description="change b",
        target_file="tests/test_x.py",
        original_content="b = 1",
        proposed_content="b = 2",
        created_at=0.0,
        confidence=1.0,
    )
    engine.apply(proposal2)
    assert len(engine.history) == 2


# ---------------------------------------------------------------------------
# Rollback & real file write
# ---------------------------------------------------------------------------


def test_apply_writes_file_when_not_dry_run() -> None:
    """In non-dry-run mode, apply writes the proposed content to disk."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".toml", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write("key = 1\n")
        tmp_path = tmp.name

    try:
        engine = EvolutionEngine(dry_run=False)
        proposal = engine.propose(
            scope=EvolutionScope.CONFIG,
            target_file=tmp_path,
            description="update value",
            proposed_content="key = 2\n",
        )
        result = engine.apply(proposal)
        assert result.applied is True

        with open(tmp_path, encoding="utf-8") as f:
            assert f.read() == "key = 2\n"
    finally:
        os.unlink(tmp_path)


def test_rollback_restores_original_content() -> None:
    """Rollback restores the original content after an apply."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".toml", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write("key = original\n")
        tmp_path = tmp.name

    try:
        engine = EvolutionEngine(dry_run=False)
        proposal = engine.propose(
            scope=EvolutionScope.CONFIG,
            target_file=tmp_path,
            description="overwrite",
            proposed_content="key = modified\n",
        )
        engine.apply(proposal)

        restored = engine.rollback(proposal)
        assert restored is True

        with open(tmp_path, encoding="utf-8") as f:
            assert f.read() == "key = original\n"
    finally:
        os.unlink(tmp_path)

"""Tests for Orchestrator.run_compiled()."""

import tempfile
from pathlib import Path

from ygn_brain.context_compiler.artifact_store import SqliteArtifactStore
from ygn_brain.orchestrator import Orchestrator


def test_run_compiled_basic():
    orch = Orchestrator()
    result = orch.run_compiled("Hello world", budget=4000)
    assert "result" in result
    assert "session_id" in result
    assert result.get("budget_used", 0) > 0
    assert result.get("within_budget") is True


def test_run_compiled_with_artifact_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SqliteArtifactStore(db_path=Path(tmpdir) / "art.db")
        try:
            orch = Orchestrator()
            result = orch.run_compiled(
                "Process this input", budget=4000, artifact_store=store,
            )
            assert "result" in result
            assert "session_id" in result
        finally:
            store.close()  # Windows: release SQLite file lock before tmpdir cleanup

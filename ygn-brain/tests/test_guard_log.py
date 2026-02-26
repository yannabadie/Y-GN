"""Tests for persistent guard log."""

import os
import tempfile

from ygn_brain.guard import GuardResult, ThreatLevel
from ygn_brain.guard_log import GuardLog


def test_guard_log_write_and_read():
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "guard_log.db")
        log = GuardLog(db_path)
        log.record(
            input_text="test input",
            result=GuardResult(
                allowed=True,
                threat_level=ThreatLevel.NONE,
                reason="ok",
                score=0.0,
            ),
            backend="RegexGuard",
        )
        entries = log.list_entries(limit=10)
        assert len(entries) == 1
        assert entries[0]["allowed"] is True
        assert entries[0]["backend"] == "RegexGuard"
        log.close()


def test_guard_log_stats():
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "guard_log.db")
        log = GuardLog(db_path)
        log.record("safe", GuardResult(True, ThreatLevel.NONE, "ok", 0.0), "Regex")
        log.record("bad", GuardResult(False, ThreatLevel.HIGH, "blocked", 80.0), "ML")
        stats = log.stats()
        assert stats["total_checks"] == 2
        assert stats["blocked"] == 1
        log.close()


def test_guard_log_empty():
    with tempfile.TemporaryDirectory() as td:
        log = GuardLog(os.path.join(td, "guard_log.db"))
        assert log.list_entries() == []
        assert log.stats()["total_checks"] == 0
        log.close()

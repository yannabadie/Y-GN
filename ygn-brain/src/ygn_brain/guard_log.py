"""Persistent guard log backed by SQLite."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

from ygn_brain.guard import GuardResult


class GuardLog:
    """SQLite-backed guard check log."""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS guard_checks (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                input_preview TEXT NOT NULL,
                threat_level TEXT NOT NULL,
                score REAL NOT NULL,
                backend TEXT NOT NULL,
                reason TEXT NOT NULL,
                allowed INTEGER NOT NULL
            )"""
        )
        self._conn.commit()

    def record(self, input_text: str, result: GuardResult, backend: str) -> None:
        self._conn.execute(
            "INSERT INTO guard_checks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex[:12],
                datetime.now(tz=UTC).isoformat(),
                input_text[:200],
                result.threat_level.value,
                result.score,
                backend,
                result.reason,
                1 if result.allowed else 0,
            ),
        )
        self._conn.commit()

    def list_entries(self, limit: int = 50, offset: int = 0) -> list[dict]:
        cursor = self._conn.execute(
            "SELECT id, timestamp, input_preview, threat_level, score, backend, reason, allowed "
            "FROM guard_checks ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        cols = [d[0] for d in cursor.description]
        entries = []
        for row in cursor.fetchall():
            entry = dict(zip(cols, row, strict=True))
            entry["allowed"] = bool(entry["allowed"])
            entries.append(entry)
        return entries

    def stats(self) -> dict:
        cursor = self._conn.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN allowed=0 THEN 1 ELSE 0 END) as blocked, "
            "AVG(score) as avg_score FROM guard_checks"
        )
        row = cursor.fetchone()
        return {
            "total_checks": row[0] or 0,
            "blocked": row[1] or 0,
            "avg_score": round(row[2] or 0.0, 2),
        }

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

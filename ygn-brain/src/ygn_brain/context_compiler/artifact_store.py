"""ArtifactStore — externalized storage for large payloads."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ArtifactHandle:
    """Lightweight reference to an externalized payload."""

    artifact_id: str
    summary: str
    size_bytes: int
    mime_type: str
    created_at: float
    source: str


def _make_summary(content: bytes, max_len: int = 200) -> str:
    """Generate summary: first ~max_len chars, truncated at word boundary."""
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        return f"[binary data, {len(content)} bytes]"
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated + "..."


def _content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class ArtifactStore(ABC):
    """Abstract store for large payloads."""

    @abstractmethod
    def store(self, content: bytes, source: str, mime_type: str = "text/plain") -> ArtifactHandle:
        ...

    @abstractmethod
    def retrieve(self, artifact_id: str) -> bytes | None:
        ...

    @abstractmethod
    def exists(self, artifact_id: str) -> bool:
        ...

    @abstractmethod
    def list_handles(self, session_id: str | None = None) -> list[ArtifactHandle]:
        ...

    @abstractmethod
    def delete(self, artifact_id: str) -> bool:
        ...


class SqliteArtifactStore(ArtifactStore):
    """SQLite-backed artifact storage."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                content BLOB NOT NULL,
                summary TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                source TEXT NOT NULL,
                session_id TEXT,
                created_at REAL NOT NULL
            )"""
        )
        self._conn.commit()

    def store(self, content: bytes, source: str, mime_type: str = "text/plain") -> ArtifactHandle:
        aid = _content_hash(content)
        now = time.time()
        summary = _make_summary(content)

        row = self._conn.execute(
            "SELECT summary, size_bytes, created_at FROM artifacts WHERE id = ?", (aid,)
        ).fetchone()
        if row:
            return ArtifactHandle(
                artifact_id=aid, summary=row[0], size_bytes=row[1],
                mime_type=mime_type, created_at=row[2], source=source,
            )

        self._conn.execute(
            "INSERT INTO artifacts"
            " (id, content, summary, size_bytes, mime_type, source, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (aid, content, summary, len(content), mime_type, source, now),
        )
        self._conn.commit()
        return ArtifactHandle(
            artifact_id=aid, summary=summary, size_bytes=len(content),
            mime_type=mime_type, created_at=now, source=source,
        )

    def retrieve(self, artifact_id: str) -> bytes | None:
        row = self._conn.execute(
            "SELECT content FROM artifacts WHERE id = ?", (artifact_id,)
        ).fetchone()
        return row[0] if row else None

    def exists(self, artifact_id: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        return row is not None

    def list_handles(self, session_id: str | None = None) -> list[ArtifactHandle]:
        if session_id:
            rows = self._conn.execute(
                "SELECT id, summary, size_bytes, mime_type, created_at, source"
                " FROM artifacts WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, summary, size_bytes, mime_type, created_at, source FROM artifacts"
            ).fetchall()
        return [
            ArtifactHandle(
                artifact_id=r[0], summary=r[1], size_bytes=r[2],
                mime_type=r[3], created_at=r[4], source=r[5],
            )
            for r in rows
        ]

    def delete(self, artifact_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()


class FsArtifactStore(ArtifactStore):
    """Filesystem-backed artifact storage with 2-char prefix directories."""

    def __init__(self, base_dir: Path | str) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _data_path(self, artifact_id: str) -> Path:
        prefix = artifact_id[:2]
        return self._base / prefix / f"{artifact_id}.dat"

    def _meta_path(self, artifact_id: str) -> Path:
        prefix = artifact_id[:2]
        return self._base / prefix / f"{artifact_id}.meta.json"

    def store(self, content: bytes, source: str, mime_type: str = "text/plain") -> ArtifactHandle:
        aid = _content_hash(content)
        now = time.time()
        summary = _make_summary(content)

        data_path = self._data_path(aid)
        meta_path = self._meta_path(aid)

        if data_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return ArtifactHandle(
                artifact_id=aid, summary=meta["summary"], size_bytes=meta["size_bytes"],
                mime_type=meta["mime_type"], created_at=meta["created_at"], source=source,
            )

        data_path.parent.mkdir(parents=True, exist_ok=True)
        data_path.write_bytes(content)
        meta = {
            "summary": summary, "size_bytes": len(content),
            "mime_type": mime_type, "source": source, "created_at": now,
        }
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        return ArtifactHandle(
            artifact_id=aid, summary=summary, size_bytes=len(content),
            mime_type=mime_type, created_at=now, source=source,
        )

    def retrieve(self, artifact_id: str) -> bytes | None:
        path = self._data_path(artifact_id)
        if not path.exists():
            return None
        return path.read_bytes()

    def exists(self, artifact_id: str) -> bool:
        return self._data_path(artifact_id).exists()

    def list_handles(self, session_id: str | None = None) -> list[ArtifactHandle]:
        handles: list[ArtifactHandle] = []
        for meta_file in self._base.rglob("*.meta.json"):
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            aid = meta_file.stem.replace(".meta", "")
            handles.append(ArtifactHandle(
                artifact_id=aid, summary=meta["summary"], size_bytes=meta["size_bytes"],
                mime_type=meta["mime_type"], created_at=meta["created_at"], source=meta["source"],
            ))
        return handles

    def delete(self, artifact_id: str) -> bool:
        data_path = self._data_path(artifact_id)
        meta_path = self._meta_path(artifact_id)
        deleted = False
        if data_path.exists():
            data_path.unlink()
            deleted = True
        if meta_path.exists():
            meta_path.unlink()
            deleted = True
        return deleted

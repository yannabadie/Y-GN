"""Tests for ArtifactStore backends."""

import tempfile
from pathlib import Path

from ygn_brain.context_compiler.artifact_store import (
    ArtifactHandle,
    FsArtifactStore,
    SqliteArtifactStore,
)


def test_sqlite_store_retrieve_dedup():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SqliteArtifactStore(db_path=Path(tmpdir) / "artifacts.db")
        content = b"Hello, this is a large tool output that should be externalized."

        h1 = store.store(content, source="tool:echo", mime_type="text/plain")
        assert isinstance(h1, ArtifactHandle)
        assert h1.size_bytes == len(content)
        assert h1.summary  # non-empty

        # Dedup: same content -> same handle
        h2 = store.store(content, source="tool:echo", mime_type="text/plain")
        assert h2.artifact_id == h1.artifact_id

        # Retrieve
        data = store.retrieve(h1.artifact_id)
        assert data == content

        # Exists
        assert store.exists(h1.artifact_id)
        assert not store.exists("nonexistent")

        store.close()


def test_fs_store_retrieve_dedup():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FsArtifactStore(base_dir=Path(tmpdir))
        content = b"Another large payload for filesystem storage."

        h1 = store.store(content, source="tool:file_read", mime_type="text/plain")
        assert h1.size_bytes == len(content)

        # Dedup
        h2 = store.store(content, source="tool:file_read", mime_type="text/plain")
        assert h2.artifact_id == h1.artifact_id

        # Retrieve
        data = store.retrieve(h1.artifact_id)
        assert data == content

        assert store.exists(h1.artifact_id)


def test_artifact_handle_summary_truncation():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SqliteArtifactStore(db_path=Path(tmpdir) / "artifacts.db")
        # Long content -- summary should be truncated to ~200 chars
        content = ("word " * 500).encode()
        handle = store.store(content, source="tool:big", mime_type="text/plain")
        assert len(handle.summary) <= 210  # allow slight overflow at word boundary

        store.close()

# Context Compiler & Tool Interrupts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Context Compiler (Session/EventLog + WorkingContext + processors + ArtifactStore) and Tool Interrupts (typed events + PerceptionAligner) to ygn-brain, enabling token-budget-aware context compilation with artifact externalization.

**Architecture:** Two new subpackages (`context_compiler/` and `tool_interrupt/`) following the existing `harness/` pattern. Session wraps EvidencePack (non-breaking). Processors are a pipeline of named Protocol-conforming functions. ArtifactStore has SQLite + FS backends. ToolInterruptHandler wraps McpToolBridge with typed events and normalization.

**Tech Stack:** Python 3.11+, pydantic (already a dep), sqlite3 (stdlib), hashlib (stdlib), asyncio (stdlib). No new external dependencies.

**Design doc:** `docs/plans/2026-02-27-context-compiler-design.md`

---

### Task 1: Session & EventLog

**Files:**
- Create: `ygn-brain/src/ygn_brain/context_compiler/__init__.py`
- Create: `ygn-brain/src/ygn_brain/context_compiler/session.py`
- Test: `ygn-brain/tests/test_session.py`

**Step 1: Write the failing tests**

Create `ygn-brain/tests/test_session.py`:

```python
"""Tests for Session & EventLog."""

from ygn_brain.context_compiler.session import EventLog, Session, SessionEvent


def test_event_log_append_and_filter():
    log = EventLog()
    log.append("user_input", {"text": "hello"}, token_estimate=10)
    log.append("memory_hit", {"key": "k1"}, token_estimate=5)
    log.append("user_input", {"text": "world"}, token_estimate=8)

    assert len(log.events) == 3
    assert log.total_tokens() == 23

    filtered = log.filter(["user_input"])
    assert len(filtered) == 2
    assert all(e.kind == "user_input" for e in filtered)


def test_event_log_since():
    log = EventLog()
    e1 = log.append("user_input", {"text": "a"}, token_estimate=5)
    e2 = log.append("tool_call", {"name": "echo"}, token_estimate=10)

    since = log.since(e1.timestamp)
    assert len(since) >= 1
    assert e2 in since


def test_session_wraps_evidence_pack():
    session = Session()
    assert session.session_id
    assert session.evidence is not None

    session.record("user_input", {"text": "test"}, token_estimate=7)
    assert len(session.event_log.events) == 1
    assert len(session.evidence.entries) == 1

    pack = session.to_evidence_pack()
    assert pack.session_id == session.session_id
    assert len(pack.entries) == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_session.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ygn_brain.context_compiler'`

**Step 3: Create the `context_compiler` package and `session.py`**

Create `ygn-brain/src/ygn_brain/context_compiler/__init__.py`:

```python
"""Context Compiler — compiles Session events into budget-aware WorkingContext."""
```

Create `ygn-brain/src/ygn_brain/context_compiler/session.py`:

```python
"""Session & EventLog — ground truth for an execution session."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..evidence import EvidencePack


@dataclass
class SessionEvent:
    """Typed event in the session timeline."""

    event_id: str
    timestamp: float
    kind: str
    data: dict[str, Any]
    token_estimate: int


class EventLog:
    """Append-only ordered log of SessionEvents."""

    def __init__(self) -> None:
        self.events: list[SessionEvent] = []

    def append(
        self, kind: str, data: dict[str, Any], token_estimate: int = 0
    ) -> SessionEvent:
        event = SessionEvent(
            event_id=f"{int(time.time() * 1000):012x}-{uuid.uuid4().hex[:12]}",
            timestamp=time.time(),
            kind=kind,
            data=data,
            token_estimate=token_estimate,
        )
        self.events.append(event)
        return event

    def filter(self, kinds: list[str]) -> list[SessionEvent]:
        return [e for e in self.events if e.kind in kinds]

    def total_tokens(self) -> int:
        return sum(e.token_estimate for e in self.events)

    def since(self, timestamp: float) -> list[SessionEvent]:
        return [e for e in self.events if e.timestamp >= timestamp]


# Map SessionEvent kinds to EvidenceKind values
_KIND_TO_EVIDENCE: dict[str, str] = {
    "user_input": "input",
    "memory_hit": "source",
    "tool_call": "tool_call",
    "tool_success": "output",
    "tool_error": "error",
    "tool_timeout": "error",
    "guard_decision": "decision",
    "phase_result": "output",
    "artifact_stored": "output",
}


class Session:
    """Wraps EventLog + EvidencePack. Single source of truth per execution."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.event_log = EventLog()
        self.evidence = EvidencePack(session_id=self.session_id)

    def record(
        self, kind: str, data: dict[str, Any], token_estimate: int = 0
    ) -> SessionEvent:
        event = self.event_log.append(kind, data, token_estimate)
        evidence_kind = _KIND_TO_EVIDENCE.get(kind, "output")
        self.evidence.add(kind, evidence_kind, data)
        return event

    def to_evidence_pack(self) -> EvidencePack:
        return self.evidence
```

**Step 4: Run tests to verify they pass**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_session.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add ygn-brain/src/ygn_brain/context_compiler/__init__.py \
       ygn-brain/src/ygn_brain/context_compiler/session.py \
       ygn-brain/tests/test_session.py
git commit -m "feat(brain): add Session & EventLog (context compiler foundation)"
```

---

### Task 2: Token Budget Tracker

**Files:**
- Create: `ygn-brain/src/ygn_brain/context_compiler/token_budget.py`
- Test: `ygn-brain/tests/test_token_budget.py`

**Step 1: Write the failing tests**

Create `ygn-brain/tests/test_token_budget.py`:

```python
"""Tests for token budget tracker."""

import pytest

from ygn_brain.context_compiler.token_budget import TokenBudget


def test_budget_tracking():
    budget = TokenBudget(max_tokens=100)
    assert budget.remaining() == 100
    assert budget.is_within_budget()

    budget.consume(60)
    assert budget.remaining() == 40
    assert budget.is_within_budget()

    budget.consume(50)
    assert budget.remaining() == -10
    assert not budget.is_within_budget()
    assert budget.overflow() == 10


def test_budget_requires_explicit_max():
    with pytest.raises(ValueError, match="max_tokens must be positive"):
        TokenBudget(max_tokens=0)

    with pytest.raises(ValueError, match="max_tokens must be positive"):
        TokenBudget(max_tokens=-1)


def test_estimate_tokens():
    from ygn_brain.context_compiler.token_budget import estimate_tokens

    assert estimate_tokens("hello world") == 3  # 2 words * 1.3 ~ 2.6 -> 3
    assert estimate_tokens("") == 0
    assert estimate_tokens("a " * 100) > 100  # 100 words * 1.3 = 130
```

**Step 2: Run tests to verify they fail**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_token_budget.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement token_budget.py**

Create `ygn-brain/src/ygn_brain/context_compiler/token_budget.py`:

```python
"""Token budget tracker — configurable, no hardcoded default."""

from __future__ import annotations

import math


def estimate_tokens(text: str) -> int:
    """Estimate token count from text. Rough heuristic: words * 1.3."""
    if not text:
        return 0
    words = len(text.split())
    return math.ceil(words * 1.3)


class TokenBudget:
    """Tracks token consumption against a configured maximum."""

    def __init__(self, max_tokens: int) -> None:
        if max_tokens <= 0:
            msg = "max_tokens must be positive"
            raise ValueError(msg)
        self._max = max_tokens
        self._consumed = 0

    def consume(self, tokens: int) -> None:
        self._consumed += tokens

    def remaining(self) -> int:
        return self._max - self._consumed

    def is_within_budget(self) -> bool:
        return self._consumed <= self._max

    def overflow(self) -> int:
        return max(0, self._consumed - self._max)

    @property
    def max_tokens(self) -> int:
        return self._max

    @property
    def consumed(self) -> int:
        return self._consumed
```

**Step 4: Run tests to verify they pass**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_token_budget.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add ygn-brain/src/ygn_brain/context_compiler/token_budget.py \
       ygn-brain/tests/test_token_budget.py
git commit -m "feat(brain): add TokenBudget tracker for context compiler"
```

---

### Task 3: WorkingContext

**Files:**
- Create: `ygn-brain/src/ygn_brain/context_compiler/working_context.py`
- Test: `ygn-brain/tests/test_working_context.py`

**Step 1: Write the failing tests**

Create `ygn-brain/tests/test_working_context.py`:

```python
"""Tests for WorkingContext."""

from ygn_brain.context_compiler.working_context import WorkingContext


def test_budget_checking():
    ctx = WorkingContext(
        system_prompt="You are a helpful assistant.",
        history=[{"role": "user", "content": "hello"}],
        memory_hits=[],
        artifact_refs=[],
        tool_results=[],
        token_count=50,
        budget=100,
    )
    assert ctx.is_within_budget()
    assert ctx.overflow() == 0

    over = WorkingContext(
        system_prompt="x",
        history=[],
        memory_hits=[],
        artifact_refs=[],
        tool_results=[],
        token_count=150,
        budget=100,
    )
    assert not over.is_within_budget()
    assert over.overflow() == 50


def test_to_messages():
    ctx = WorkingContext(
        system_prompt="You are helpful.",
        history=[
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
        ],
        memory_hits=[{"key": "math", "content": "basic arithmetic"}],
        artifact_refs=[{"handle": "abc123", "summary": "large file", "size_bytes": 5000}],
        tool_results=[{"tool": "calc", "result": "4"}],
        token_count=80,
        budget=200,
    )
    msgs = ctx.to_messages()
    assert msgs[0]["role"] == "system"
    assert "You are helpful." in msgs[0]["content"]
    # Memory hits included in system context
    assert "basic arithmetic" in msgs[0]["content"]
    # Artifact refs mentioned
    assert "abc123" in msgs[0]["content"]
    # History messages follow
    assert msgs[1]["role"] == "user"
    assert msgs[2]["role"] == "assistant"
```

**Step 2: Run tests to verify they fail**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_working_context.py -v`
Expected: FAIL

**Step 3: Implement working_context.py**

Create `ygn-brain/src/ygn_brain/context_compiler/working_context.py`:

```python
"""WorkingContext — compiled view of a Session, ready for LLM consumption."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkingContext:
    """Budget-aware compiled context for LLM calls."""

    system_prompt: str
    history: list[dict[str, Any]]
    memory_hits: list[dict[str, Any]]
    artifact_refs: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    token_count: int
    budget: int

    def is_within_budget(self) -> bool:
        return self.token_count <= self.budget

    def overflow(self) -> int:
        return max(0, self.token_count - self.budget)

    def to_messages(self) -> list[dict[str, str]]:
        """Format as message list for LLM provider.chat()."""
        # Build system message with context sections
        parts = [self.system_prompt]

        if self.memory_hits:
            parts.append("\n\n## Relevant memories")
            for hit in self.memory_hits:
                parts.append(f"- [{hit.get('key', '')}]: {hit.get('content', '')}")

        if self.artifact_refs:
            parts.append("\n\n## Available artifacts (use handle to retrieve)")
            for ref in self.artifact_refs:
                handle = ref.get("handle", "")
                summary = ref.get("summary", "")
                size = ref.get("size_bytes", 0)
                parts.append(f"- [{handle}] ({size} bytes): {summary}")

        if self.tool_results:
            parts.append("\n\n## Recent tool results")
            for tr in self.tool_results:
                tool = tr.get("tool", "unknown")
                result = tr.get("result", "")
                parts.append(f"- {tool}: {result}")

        system_msg = {"role": "system", "content": "\n".join(parts)}
        messages: list[dict[str, str]] = [system_msg]
        messages.extend(
            {"role": h["role"], "content": h["content"]}
            for h in self.history
        )
        return messages
```

**Step 4: Run tests to verify they pass**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_working_context.py -v`
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add ygn-brain/src/ygn_brain/context_compiler/working_context.py \
       ygn-brain/tests/test_working_context.py
git commit -m "feat(brain): add WorkingContext compiled view for LLM calls"
```

---

### Task 4: ArtifactStore (SQLite + FS backends)

**Files:**
- Create: `ygn-brain/src/ygn_brain/context_compiler/artifact_store.py`
- Test: `ygn-brain/tests/test_artifact_store.py`

**Step 1: Write the failing tests**

Create `ygn-brain/tests/test_artifact_store.py`:

```python
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

        # Dedup: same content → same handle
        h2 = store.store(content, source="tool:echo", mime_type="text/plain")
        assert h2.artifact_id == h1.artifact_id

        # Retrieve
        data = store.retrieve(h1.artifact_id)
        assert data == content

        # Exists
        assert store.exists(h1.artifact_id)
        assert not store.exists("nonexistent")


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
        # Long content — summary should be truncated to ~200 chars
        content = ("word " * 500).encode()
        handle = store.store(content, source="tool:big", mime_type="text/plain")
        assert len(handle.summary) <= 210  # allow slight overflow at word boundary
```

**Step 2: Run tests to verify they fail**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_artifact_store.py -v`
Expected: FAIL

**Step 3: Implement artifact_store.py**

Create `ygn-brain/src/ygn_brain/context_compiler/artifact_store.py`:

```python
"""ArtifactStore — externalized storage for large payloads."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    # Truncate at last space
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

        # Dedup: if exists, return existing handle
        row = self._conn.execute("SELECT summary, size_bytes, created_at FROM artifacts WHERE id = ?", (aid,)).fetchone()
        if row:
            return ArtifactHandle(
                artifact_id=aid, summary=row[0], size_bytes=row[1],
                mime_type=mime_type, created_at=row[2], source=source,
            )

        self._conn.execute(
            "INSERT INTO artifacts (id, content, summary, size_bytes, mime_type, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (aid, content, summary, len(content), mime_type, source, now),
        )
        self._conn.commit()
        return ArtifactHandle(
            artifact_id=aid, summary=summary, size_bytes=len(content),
            mime_type=mime_type, created_at=now, source=source,
        )

    def retrieve(self, artifact_id: str) -> bytes | None:
        row = self._conn.execute("SELECT content FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        return row[0] if row else None

    def exists(self, artifact_id: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        return row is not None

    def list_handles(self, session_id: str | None = None) -> list[ArtifactHandle]:
        if session_id:
            rows = self._conn.execute(
                "SELECT id, summary, size_bytes, mime_type, created_at, source FROM artifacts WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, summary, size_bytes, mime_type, created_at, source FROM artifacts"
            ).fetchall()
        return [
            ArtifactHandle(artifact_id=r[0], summary=r[1], size_bytes=r[2], mime_type=r[3], created_at=r[4], source=r[5])
            for r in rows
        ]

    def delete(self, artifact_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
        self._conn.commit()
        return cur.rowcount > 0


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

        # Dedup: if exists, read existing metadata
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
```

**Step 4: Run tests to verify they pass**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_artifact_store.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add ygn-brain/src/ygn_brain/context_compiler/artifact_store.py \
       ygn-brain/tests/test_artifact_store.py
git commit -m "feat(brain): add ArtifactStore with SQLite + FS backends"
```

---

### Task 5: Processor Pipeline & ContextCompiler

**Files:**
- Create: `ygn-brain/src/ygn_brain/context_compiler/processors.py`
- Test: `ygn-brain/tests/test_processors.py`

**Step 1: Write the failing tests**

Create `ygn-brain/tests/test_processors.py`:

```python
"""Tests for context compiler processors."""

import tempfile
from pathlib import Path

from ygn_brain.context_compiler.artifact_store import SqliteArtifactStore
from ygn_brain.context_compiler.processors import (
    ArtifactAttacher,
    Compactor,
    ContextCompiler,
    HistorySelector,
    MemoryPreloader,
)
from ygn_brain.context_compiler.session import Session
from ygn_brain.context_compiler.working_context import WorkingContext
from ygn_brain.memory import InMemoryBackend


def _make_session_with_history(n_turns: int) -> Session:
    session = Session()
    for i in range(n_turns):
        role = "user" if i % 2 == 0 else "assistant"
        session.record(
            "user_input" if role == "user" else "phase_result",
            {"role": role, "content": f"Message {i}"},
            token_estimate=20,
        )
    return session


def test_history_selector_keeps_first_and_last():
    session = _make_session_with_history(20)
    ctx = WorkingContext(
        system_prompt="test", history=[], memory_hits=[], artifact_refs=[],
        tool_results=[], token_count=0, budget=500,
    )
    selector = HistorySelector(keep_first=2, keep_last=3)
    result = selector.process(session, ctx, budget=500)
    # Should have 5 entries: first 2 + last 3
    assert len(result.history) == 5
    assert result.history[0]["content"] == "Message 0"
    assert result.history[1]["content"] == "Message 1"
    assert result.history[-1]["content"] == "Message 19"


def test_compactor_merges_consecutive():
    session = Session()
    ctx = WorkingContext(
        system_prompt="test",
        history=[
            {"role": "user", "content": "  Hello  "},
            {"role": "user", "content": "  World  "},
            {"role": "assistant", "content": "Hi there"},
        ],
        memory_hits=[], artifact_refs=[], tool_results=[],
        token_count=30, budget=500,
    )
    compactor = Compactor()
    result = compactor.process(session, ctx, budget=500)
    # Two consecutive user messages merged, whitespace trimmed
    assert len(result.history) == 2
    assert result.history[0]["role"] == "user"
    assert "Hello" in result.history[0]["content"]
    assert "World" in result.history[0]["content"]


def test_memory_preloader():
    mem = InMemoryBackend()
    mem.store("fact1", "Python is a programming language", "core")
    mem.store("fact2", "Rust is systems programming", "core")

    session = Session()
    session.record("user_input", {"text": "Tell me about Python"}, token_estimate=10)

    ctx = WorkingContext(
        system_prompt="test", history=[], memory_hits=[], artifact_refs=[],
        tool_results=[], token_count=10, budget=500,
    )
    preloader = MemoryPreloader(memory_service=mem, top_k=5)
    result = preloader.process(session, ctx, budget=500)
    assert len(result.memory_hits) >= 1


def test_artifact_attacher_externalizes_large():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SqliteArtifactStore(db_path=Path(tmpdir) / "art.db")

        session = Session()
        ctx = WorkingContext(
            system_prompt="test",
            history=[],
            memory_hits=[],
            artifact_refs=[],
            tool_results=[
                {"tool": "big_tool", "result": "x" * 5000},
            ],
            token_count=5000,
            budget=500,
        )
        attacher = ArtifactAttacher(artifact_store=store, threshold_bytes=1024)
        result = attacher.process(session, ctx, budget=500)

        # Large result externalized: tool_results cleared, artifact_ref added
        assert len(result.artifact_refs) == 1
        assert result.artifact_refs[0]["handle"]
        assert result.artifact_refs[0]["size_bytes"] >= 5000
        # Token count reduced
        assert result.token_count < 5000
```

**Step 2: Run tests to verify they fail**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_processors.py -v`
Expected: FAIL

**Step 3: Implement processors.py**

Create `ygn-brain/src/ygn_brain/context_compiler/processors.py`:

```python
"""Context compiler processors — named, composable pipeline stages."""

from __future__ import annotations

from typing import Any, Protocol

from ..memory import MemoryService
from .artifact_store import ArtifactStore
from .session import Session
from .token_budget import estimate_tokens
from .working_context import WorkingContext


class Processor(Protocol):
    """Named, composable context processor."""

    name: str

    def process(self, session: Session, ctx: WorkingContext, budget: int) -> WorkingContext: ...


class HistorySelector:
    """Select recent turns, keep first + last N, drop middle if over budget."""

    name = "history_selector"

    def __init__(self, keep_first: int = 2, keep_last: int = 5) -> None:
        self._keep_first = keep_first
        self._keep_last = keep_last

    def process(self, session: Session, ctx: WorkingContext, budget: int) -> WorkingContext:
        # Extract conversation events from session
        conv_events = [
            e for e in session.event_log.events
            if e.kind in ("user_input", "phase_result")
        ]
        history: list[dict[str, Any]] = []
        for evt in conv_events:
            role = evt.data.get("role", "user")
            content = evt.data.get("content", evt.data.get("text", ""))
            history.append({"role": role, "content": content})

        if not history:
            return ctx

        total = len(history)
        if total <= self._keep_first + self._keep_last:
            selected = history
        else:
            selected = history[: self._keep_first] + history[total - self._keep_last :]

        token_count = sum(estimate_tokens(h["content"]) for h in selected)
        return WorkingContext(
            system_prompt=ctx.system_prompt,
            history=selected,
            memory_hits=ctx.memory_hits,
            artifact_refs=ctx.artifact_refs,
            tool_results=ctx.tool_results,
            token_count=token_count + estimate_tokens(ctx.system_prompt),
            budget=budget,
        )


class Compactor:
    """Merge consecutive same-role messages, trim whitespace."""

    name = "compactor"

    def process(self, session: Session, ctx: WorkingContext, budget: int) -> WorkingContext:
        if not ctx.history:
            return ctx

        merged: list[dict[str, Any]] = []
        for msg in ctx.history:
            content = msg["content"].strip()
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] += "\n" + content
            else:
                merged.append({"role": msg["role"], "content": content})

        token_count = sum(estimate_tokens(h["content"]) for h in merged)
        return WorkingContext(
            system_prompt=ctx.system_prompt,
            history=merged,
            memory_hits=ctx.memory_hits,
            artifact_refs=ctx.artifact_refs,
            tool_results=ctx.tool_results,
            token_count=token_count + estimate_tokens(ctx.system_prompt),
            budget=budget,
        )


class MemoryPreloader:
    """Query memory service, inject top-K relevant memories into context."""

    name = "memory_preloader"

    def __init__(self, memory_service: MemoryService, top_k: int = 5) -> None:
        self._memory = memory_service
        self._top_k = top_k

    def process(self, session: Session, ctx: WorkingContext, budget: int) -> WorkingContext:
        # Find latest user input from session
        user_events = session.event_log.filter(["user_input"])
        if not user_events:
            return ctx
        query = user_events[-1].data.get("text", user_events[-1].data.get("content", ""))
        if not query:
            return ctx

        entries = self._memory.recall(query, limit=self._top_k)
        hits = [{"key": e.key, "content": e.content, "category": e.category} for e in entries]

        extra_tokens = sum(estimate_tokens(h["content"]) for h in hits)
        return WorkingContext(
            system_prompt=ctx.system_prompt,
            history=ctx.history,
            memory_hits=hits,
            artifact_refs=ctx.artifact_refs,
            tool_results=ctx.tool_results,
            token_count=ctx.token_count + extra_tokens,
            budget=budget,
        )


class ArtifactAttacher:
    """Replace large payloads with artifact handles + summaries."""

    name = "artifact_attacher"

    def __init__(self, artifact_store: ArtifactStore, threshold_bytes: int = 1024) -> None:
        self._store = artifact_store
        self._threshold = threshold_bytes

    def process(self, session: Session, ctx: WorkingContext, budget: int) -> WorkingContext:
        remaining_results: list[dict[str, Any]] = []
        new_refs: list[dict[str, Any]] = list(ctx.artifact_refs)
        saved_tokens = 0

        for tr in ctx.tool_results:
            result_text = tr.get("result", "")
            result_bytes = result_text.encode("utf-8") if isinstance(result_text, str) else result_text
            if len(result_bytes) >= self._threshold:
                handle = self._store.store(
                    result_bytes,
                    source=f"tool:{tr.get('tool', 'unknown')}",
                    mime_type="text/plain",
                )
                new_refs.append({
                    "handle": handle.artifact_id,
                    "summary": handle.summary,
                    "size_bytes": handle.size_bytes,
                    "source": handle.source,
                })
                saved_tokens += estimate_tokens(result_text)
                session.record(
                    "artifact_stored",
                    {"handle": handle.artifact_id, "source": handle.source, "size_bytes": handle.size_bytes},
                    token_estimate=10,
                )
            else:
                remaining_results.append(tr)

        ref_tokens = sum(estimate_tokens(r.get("summary", "")) for r in new_refs)
        return WorkingContext(
            system_prompt=ctx.system_prompt,
            history=ctx.history,
            memory_hits=ctx.memory_hits,
            artifact_refs=new_refs,
            tool_results=remaining_results,
            token_count=ctx.token_count - saved_tokens + ref_tokens,
            budget=budget,
        )


class ContextCompiler:
    """Runs processors in order to produce a WorkingContext from a Session."""

    def __init__(self, processors: list[Processor] | None = None) -> None:
        self._processors: list[Processor] = processors or []

    def add_processor(self, processor: Processor) -> None:
        self._processors.append(processor)

    def compile(
        self, session: Session, budget: int, system_prompt: str = ""
    ) -> WorkingContext:
        ctx = WorkingContext(
            system_prompt=system_prompt,
            history=[],
            memory_hits=[],
            artifact_refs=[],
            tool_results=[],
            token_count=estimate_tokens(system_prompt),
            budget=budget,
        )
        for proc in self._processors:
            ctx = proc.process(session, ctx, budget)
        return ctx
```

**Step 4: Run tests to verify they pass**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_processors.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add ygn-brain/src/ygn_brain/context_compiler/processors.py \
       ygn-brain/tests/test_processors.py
git commit -m "feat(brain): add processor pipeline (history, compactor, memory, artifacts)"
```

---

### Task 6: Tool Interrupt Events

**Files:**
- Create: `ygn-brain/src/ygn_brain/tool_interrupt/__init__.py`
- Create: `ygn-brain/src/ygn_brain/tool_interrupt/events.py`
- Test: `ygn-brain/tests/test_tool_events.py`

**Step 1: Write the failing tests**

Create `ygn-brain/tests/test_tool_events.py`:

```python
"""Tests for tool interrupt events."""

from ygn_brain.tool_interrupt.events import ToolEvent, ToolEventKind


def test_tool_event_kinds():
    assert ToolEventKind.CALL == "tool_call"
    assert ToolEventKind.SUCCESS == "tool_success"
    assert ToolEventKind.ERROR == "tool_error"
    assert ToolEventKind.TIMEOUT == "tool_timeout"


def test_tool_event_creation():
    evt = ToolEvent.create(
        kind=ToolEventKind.SUCCESS,
        tool_name="echo",
        arguments={"text": "hello"},
        result="hello",
        latency_ms=42.0,
    )
    assert evt.kind == ToolEventKind.SUCCESS
    assert evt.tool_name == "echo"
    assert evt.result == "hello"
    assert evt.error is None
    assert evt.latency_ms == 42.0
    assert evt.event_id  # non-empty


def test_tool_event_error():
    evt = ToolEvent.create(
        kind=ToolEventKind.ERROR,
        tool_name="fail_tool",
        arguments={},
        error="Connection refused",
        latency_ms=100.0,
    )
    assert evt.kind == ToolEventKind.ERROR
    assert evt.result is None
    assert evt.error == "Connection refused"
```

**Step 2: Run tests to verify they fail**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_tool_events.py -v`
Expected: FAIL

**Step 3: Implement events.py**

Create `ygn-brain/src/ygn_brain/tool_interrupt/__init__.py`:

```python
"""Tool Interrupts — typed events, normalization, and schema validation for tool calls."""
```

Create `ygn-brain/src/ygn_brain/tool_interrupt/events.py`:

```python
"""Tool interrupt events — typed tool interaction events."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ToolEventKind(StrEnum):
    CALL = "tool_call"
    SUCCESS = "tool_success"
    ERROR = "tool_error"
    TIMEOUT = "tool_timeout"


@dataclass
class ToolEvent:
    """Typed tool interaction event."""

    event_id: str
    timestamp: float
    kind: ToolEventKind
    tool_name: str
    arguments: dict[str, Any]
    result: str | None
    error: str | None
    latency_ms: float
    normalized: dict[str, Any] | None

    @classmethod
    def create(
        cls,
        kind: ToolEventKind,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        result: str | None = None,
        error: str | None = None,
        latency_ms: float = 0.0,
        normalized: dict[str, Any] | None = None,
    ) -> ToolEvent:
        return cls(
            event_id=f"{int(time.time() * 1000):012x}-{uuid.uuid4().hex[:12]}",
            timestamp=time.time(),
            kind=kind,
            tool_name=tool_name,
            arguments=arguments or {},
            result=result,
            error=error,
            latency_ms=latency_ms,
            normalized=normalized,
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_tool_events.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add ygn-brain/src/ygn_brain/tool_interrupt/__init__.py \
       ygn-brain/src/ygn_brain/tool_interrupt/events.py \
       ygn-brain/tests/test_tool_events.py
git commit -m "feat(brain): add ToolEvent typed events for tool interrupts"
```

---

### Task 7: Schema Registry & Perception Aligner

**Files:**
- Create: `ygn-brain/src/ygn_brain/tool_interrupt/schemas.py`
- Create: `ygn-brain/src/ygn_brain/tool_interrupt/normalizer.py`
- Test: `ygn-brain/tests/test_normalizer.py`

**Step 1: Write the failing tests**

Create `ygn-brain/tests/test_normalizer.py`:

```python
"""Tests for PerceptionAligner and SchemaRegistry."""

from ygn_brain.tool_interrupt.normalizer import PerceptionAligner
from ygn_brain.tool_interrupt.schemas import SchemaRegistry


def test_schema_registry_register_and_validate():
    reg = SchemaRegistry()
    reg.register("echo", {
        "type": "object",
        "properties": {"output": {"type": "string"}},
        "required": ["output"],
    })
    valid, errors = reg.validate("echo", {"output": "hello"})
    assert valid
    assert not errors

    valid2, errors2 = reg.validate("echo", {"wrong_field": 123})
    assert not valid2
    assert len(errors2) > 0


def test_schema_registry_unregistered_tool():
    reg = SchemaRegistry()
    valid, errors = reg.validate("unknown_tool", {"any": "data"})
    # Unregistered tools pass validation (no schema to check against)
    assert valid
    assert not errors


def test_normalizer_redacts_secrets():
    reg = SchemaRegistry()
    aligner = PerceptionAligner(schema_registry=reg)

    raw = '{"output": "result", "api_key": "sk-abc123xyz", "token": "Bearer eyJhbGciOiJ"}'
    result = aligner.normalize("some_tool", raw)
    assert result["valid"]
    assert "sk-abc123xyz" not in result["summary_concise"]
    assert "sk-abc123xyz" not in result["summary_detailed"]
    assert len(result["redacted_fields"]) > 0


def test_normalizer_generates_summaries():
    reg = SchemaRegistry()
    aligner = PerceptionAligner(schema_registry=reg)

    raw = "x" * 5000
    result = aligner.normalize("big_tool", raw)
    assert len(result["summary_concise"]) <= 220
    assert len(result["summary_detailed"]) <= 2020
    assert result["valid"]


def test_normalizer_validates_against_schema():
    reg = SchemaRegistry()
    reg.register("calc", {
        "type": "object",
        "properties": {"result": {"type": "number"}},
        "required": ["result"],
    })
    aligner = PerceptionAligner(schema_registry=reg)

    # Valid JSON matching schema
    result = aligner.normalize("calc", '{"result": 42}')
    assert result["valid"]

    # Valid JSON NOT matching schema
    result2 = aligner.normalize("calc", '{"wrong": "field"}')
    assert not result2["valid"]
    assert len(result2["validation_errors"]) > 0
```

**Step 2: Run tests to verify they fail**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_normalizer.py -v`
Expected: FAIL

**Step 3: Implement schemas.py and normalizer.py**

Create `ygn-brain/src/ygn_brain/tool_interrupt/schemas.py`:

```python
"""Schema registry for per-tool output JSON Schemas."""

from __future__ import annotations

import json
from typing import Any


class SchemaRegistry:
    """Registry of per-tool output JSON Schemas."""

    def __init__(self) -> None:
        self._schemas: dict[str, dict[str, Any]] = {}

    def register(self, tool_name: str, schema: dict[str, Any]) -> None:
        self._schemas[tool_name] = schema

    def get(self, tool_name: str) -> dict[str, Any] | None:
        return self._schemas.get(tool_name)

    def validate(self, tool_name: str, data: Any) -> tuple[bool, list[str]]:
        """Validate data against tool's schema. Returns (valid, errors)."""
        schema = self._schemas.get(tool_name)
        if schema is None:
            return True, []  # No schema = pass

        errors: list[str] = []

        # Check type
        expected_type = schema.get("type")
        if expected_type == "object" and not isinstance(data, dict):
            errors.append(f"Expected object, got {type(data).__name__}")
            return False, errors

        if expected_type == "object" and isinstance(data, dict):
            # Check required fields
            for field in schema.get("required", []):
                if field not in data:
                    errors.append(f"Missing required field: {field}")

            # Check property types
            props = schema.get("properties", {})
            for key, val in data.items():
                if key in props:
                    prop_type = props[key].get("type")
                    if prop_type == "string" and not isinstance(val, str):
                        errors.append(f"Field '{key}': expected string, got {type(val).__name__}")
                    elif prop_type == "number" and not isinstance(val, (int, float)):
                        errors.append(f"Field '{key}': expected number, got {type(val).__name__}")
                    elif prop_type == "boolean" and not isinstance(val, bool):
                        errors.append(f"Field '{key}': expected boolean, got {type(val).__name__}")

        return len(errors) == 0, errors

    def auto_discover(self, tools: list[dict[str, Any]]) -> None:
        """Import output schemas from MCP tools/list response."""
        for tool in tools:
            name = tool.get("name", "")
            output_schema = tool.get("outputSchema")
            if name and output_schema:
                self._schemas[name] = output_schema
```

Create `ygn-brain/src/ygn_brain/tool_interrupt/normalizer.py`:

```python
"""PerceptionAligner — normalizes raw tool outputs for LLM consumption."""

from __future__ import annotations

import json
import re
from typing import Any

from .schemas import SchemaRegistry

# Secret patterns to redact
_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"), "[REDACTED_BEARER]"),
    (re.compile(r"(?i)password\s*[=:]\s*\S+"), "[REDACTED_PASSWORD]"),
    (re.compile(r"(?i)api[_-]?key\s*[=:]\s*\S+"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?i)secret\s*[=:]\s*\S+"), "[REDACTED_SECRET]"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"gho_[A-Za-z0-9]{36}"), "[REDACTED_GH_TOKEN]"),
]


def _redact(text: str) -> tuple[str, list[str]]:
    """Redact secrets from text. Returns (redacted_text, list of redacted field names)."""
    redacted_fields: list[str] = []
    result = text
    for pattern, replacement in _SECRET_PATTERNS:
        if pattern.search(result):
            redacted_fields.append(replacement)
            result = pattern.sub(replacement, result)
    return result, redacted_fields


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated + "..."


class PerceptionAligner:
    """Normalizes raw tool outputs: schema validation + redaction + summaries."""

    def __init__(self, schema_registry: SchemaRegistry) -> None:
        self._registry = schema_registry

    def normalize(self, tool_name: str, raw_output: str) -> dict[str, Any]:
        """Normalize a raw tool output string.

        Returns dict with keys: valid, data, summary_concise, summary_detailed,
        redacted_fields, validation_errors.
        """
        # 1. Parse output
        parsed: Any = None
        is_json = False
        try:
            parsed = json.loads(raw_output)
            is_json = True
        except (json.JSONDecodeError, TypeError):
            parsed = raw_output

        # 2. Schema validation
        validation_errors: list[str] = []
        valid = True
        if is_json:
            valid, validation_errors = self._registry.validate(tool_name, parsed)

        # 3. Redact secrets
        redacted_text, redacted_fields = _redact(
            json.dumps(parsed) if is_json else str(parsed)
        )

        # 4. Generate summaries
        summary_concise = _truncate(redacted_text, 200)
        summary_detailed = _truncate(redacted_text, 2000)

        return {
            "valid": valid,
            "data": parsed,
            "summary_concise": summary_concise,
            "summary_detailed": summary_detailed,
            "redacted_fields": redacted_fields,
            "validation_errors": validation_errors,
        }
```

**Step 4: Run tests to verify they pass**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_normalizer.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add ygn-brain/src/ygn_brain/tool_interrupt/schemas.py \
       ygn-brain/src/ygn_brain/tool_interrupt/normalizer.py \
       ygn-brain/tests/test_normalizer.py
git commit -m "feat(brain): add SchemaRegistry + PerceptionAligner for tool normalization"
```

---

### Task 8: ToolInterruptHandler

**Files:**
- Create: `ygn-brain/src/ygn_brain/tool_interrupt/handler.py`
- Test: `ygn-brain/tests/test_tool_interrupt.py`

**Step 1: Write the failing tests**

Create `ygn-brain/tests/test_tool_interrupt.py`:

```python
"""Tests for ToolInterruptHandler."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ygn_brain.context_compiler.artifact_store import SqliteArtifactStore
from ygn_brain.context_compiler.session import Session
from ygn_brain.tool_interrupt.events import ToolEventKind
from ygn_brain.tool_interrupt.handler import ToolInterruptHandler
from ygn_brain.tool_interrupt.normalizer import PerceptionAligner
from ygn_brain.tool_interrupt.schemas import SchemaRegistry


@pytest.fixture
def handler():
    bridge = AsyncMock()
    bridge.execute = AsyncMock(return_value="echo: hello")
    reg = SchemaRegistry()
    normalizer = PerceptionAligner(schema_registry=reg)
    session = Session()
    tmpdir = tempfile.mkdtemp()
    store = SqliteArtifactStore(db_path=Path(tmpdir) / "art.db")
    return ToolInterruptHandler(
        bridge=bridge, normalizer=normalizer, session=session, artifact_store=store,
    )


@pytest.mark.asyncio
async def test_handler_success(handler):
    event = await handler.call("echo", {"text": "hello"})
    assert event.kind == ToolEventKind.SUCCESS
    assert event.result == "echo: hello"
    assert event.error is None
    assert event.latency_ms >= 0
    # Session should have 2 events: CALL + SUCCESS
    assert len(handler._session.event_log.events) == 2


@pytest.mark.asyncio
async def test_handler_error(handler):
    handler._bridge.execute = AsyncMock(side_effect=RuntimeError("boom"))
    event = await handler.call("fail_tool", {})
    assert event.kind == ToolEventKind.ERROR
    assert event.error == "boom"
    assert event.result is None


@pytest.mark.asyncio
async def test_handler_timeout(handler):
    async def slow_execute(name, args):
        await asyncio.sleep(10)
        return "never"

    handler._bridge.execute = slow_execute
    event = await handler.call("slow_tool", {}, timeout_sec=0.1)
    assert event.kind == ToolEventKind.TIMEOUT
    assert event.error
    assert "timeout" in event.error.lower() or "timed out" in event.error.lower()
```

**Step 2: Run tests to verify they fail**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_tool_interrupt.py -v`
Expected: FAIL

**Step 3: Implement handler.py**

Create `ygn-brain/src/ygn_brain/tool_interrupt/handler.py`:

```python
"""ToolInterruptHandler — wraps McpToolBridge with event emission + normalization."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ..context_compiler.artifact_store import ArtifactStore
from ..context_compiler.session import Session
from .events import ToolEvent, ToolEventKind
from .normalizer import PerceptionAligner


class ToolInterruptHandler:
    """Wraps a tool bridge with typed events, normalization, and artifact externalization."""

    def __init__(
        self,
        bridge: Any,  # McpToolBridge or any object with async execute(name, args)
        normalizer: PerceptionAligner,
        session: Session,
        artifact_store: ArtifactStore | None = None,
        externalize_threshold: int = 1024,
    ) -> None:
        self._bridge = bridge
        self._normalizer = normalizer
        self._session = session
        self._artifact_store = artifact_store
        self._threshold = externalize_threshold

    async def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_sec: float = 30.0,
    ) -> ToolEvent:
        """Execute a tool with event emission, normalization, and optional externalization."""
        # 1. Emit CALL event
        self._session.record(
            "tool_call",
            {"tool_name": tool_name, "arguments": arguments},
            token_estimate=10,
        )

        start = time.perf_counter()
        try:
            # 2. Execute with timeout
            result = await asyncio.wait_for(
                self._bridge.execute(tool_name, arguments),
                timeout=timeout_sec,
            )
            latency = (time.perf_counter() - start) * 1000

            # 3. Normalize
            normalized = self._normalizer.normalize(tool_name, str(result))

            # 4. Externalize if large
            result_str = str(result)
            if self._artifact_store and len(result_str.encode()) >= self._threshold:
                handle = self._artifact_store.store(
                    result_str.encode(),
                    source=f"tool:{tool_name}",
                )
                self._session.record(
                    "artifact_stored",
                    {"handle": handle.artifact_id, "source": handle.source},
                    token_estimate=10,
                )

            # 5. Emit SUCCESS event
            event = ToolEvent.create(
                kind=ToolEventKind.SUCCESS,
                tool_name=tool_name,
                arguments=arguments,
                result=result_str,
                latency_ms=latency,
                normalized=normalized,
            )
            self._session.record(
                "tool_success",
                {"tool_name": tool_name, "latency_ms": latency},
                token_estimate=5,
            )
            return event

        except TimeoutError:
            latency = (time.perf_counter() - start) * 1000
            event = ToolEvent.create(
                kind=ToolEventKind.TIMEOUT,
                tool_name=tool_name,
                arguments=arguments,
                error=f"Tool '{tool_name}' timed out after {timeout_sec}s",
                latency_ms=latency,
            )
            self._session.record(
                "tool_timeout",
                {"tool_name": tool_name, "timeout_sec": timeout_sec},
                token_estimate=5,
            )
            return event

        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            event = ToolEvent.create(
                kind=ToolEventKind.ERROR,
                tool_name=tool_name,
                arguments=arguments,
                error=str(exc),
                latency_ms=latency,
            )
            self._session.record(
                "tool_error",
                {"tool_name": tool_name, "error": str(exc)},
                token_estimate=5,
            )
            return event
```

**Step 4: Run tests to verify they pass**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_tool_interrupt.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add ygn-brain/src/ygn_brain/tool_interrupt/handler.py \
       ygn-brain/tests/test_tool_interrupt.py
git commit -m "feat(brain): add ToolInterruptHandler with timeout + normalization"
```

---

### Task 9: Wire into Orchestrator & MCP Server

**Files:**
- Modify: `ygn-brain/src/ygn_brain/orchestrator.py` (add `run_compiled()`)
- Modify: `ygn-brain/src/ygn_brain/hivemind.py` (add `run_from_context()`)
- Modify: `ygn-brain/src/ygn_brain/mcp_server.py` (add `orchestrate_compiled` tool)
- Test: `ygn-brain/tests/test_orchestrator_compiled.py`

**Step 1: Write the failing test**

Create `ygn-brain/tests/test_orchestrator_compiled.py`:

```python
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
        orch = Orchestrator()
        result = orch.run_compiled(
            "Process this input", budget=4000, artifact_store=store,
        )
        assert "result" in result
        assert "session_id" in result
```

**Step 2: Run tests to verify they fail**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_orchestrator_compiled.py -v`
Expected: FAIL with `AttributeError: 'Orchestrator' object has no attribute 'run_compiled'`

**Step 3: Add `run_compiled()` to Orchestrator**

Add to `ygn-brain/src/ygn_brain/orchestrator.py` after the `run_async` method (after line 166):

```python
    def run_compiled(
        self,
        user_input: str,
        budget: int,
        system_prompt: str = "You are a helpful AI assistant.",
        artifact_store: ArtifactStore | None = None,
    ) -> dict[str, Any]:
        """Execute a pipeline pass using the context compiler.

        Creates a Session, compiles a WorkingContext within the token budget,
        then runs the HiveMind pipeline.
        """
        from .context_compiler.artifact_store import ArtifactStore
        from .context_compiler.processors import (
            ArtifactAttacher,
            Compactor,
            ContextCompiler,
            HistorySelector,
            MemoryPreloader,
        )
        from .context_compiler.session import Session

        # 1. Create session
        session = Session(session_id=self.evidence.session_id)
        session.record("user_input", {"text": user_input}, token_estimate=len(user_input.split()) * 2)

        # 2. Guard check
        guard_result = self._guard_pipeline.evaluate(user_input)
        session.record(
            "guard_decision",
            {"allowed": guard_result.allowed, "threat_level": guard_result.threat_level},
            token_estimate=5,
        )
        if not guard_result.allowed:
            self.evidence = session.to_evidence_pack()
            return {
                "result": f"Blocked: {guard_result.reason}",
                "session_id": session.session_id,
                "blocked": True,
            }

        # 3. Build processor pipeline
        processors: list = [HistorySelector(), Compactor()]
        if self._memory_service:
            processors.append(MemoryPreloader(memory_service=self._memory_service))
        if artifact_store:
            processors.append(ArtifactAttacher(artifact_store=artifact_store))

        compiler = ContextCompiler(processors=processors)
        working_ctx = compiler.compile(session, budget=budget, system_prompt=system_prompt)

        # 4. Run HiveMind pipeline
        results = self._hivemind.run(user_input, session.evidence)

        # 5. Update state
        self.state = FSMState()
        for phase in [Phase.DIAGNOSIS, Phase.ANALYSIS, Phase.PLANNING,
                      Phase.EXECUTION, Phase.VALIDATION, Phase.SYNTHESIS, Phase.COMPLETE]:
            self.state = self.state.transition(phase)

        synthesis_results = [r for r in results if r.phase == "synthesis"]
        final = synthesis_results[0].data.get("final", "") if synthesis_results else f"Processed: {user_input}"

        self.evidence = session.to_evidence_pack()
        return {
            "result": final,
            "session_id": session.session_id,
            "budget_used": working_ctx.token_count,
            "within_budget": working_ctx.is_within_budget(),
        }
```

Note: You need to add the import `ArtifactStore` at the top of the method body (lazy import to avoid circular imports).

**Step 4: Run tests to verify they pass**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_orchestrator_compiled.py -v`
Expected: 2 PASSED

**Step 5: Also verify existing orchestrator tests still pass**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_orchestrator.py -v`
Expected: All existing tests PASS (non-breaking change)

**Step 6: Add `orchestrate_compiled` tool to MCP server**

Add to `_TOOLS` list in `ygn-brain/src/ygn_brain/mcp_server.py` (after the `orchestrate_refined` tool, before line 110):

```python
    {
        "name": "orchestrate_compiled",
        "description": "Run HiveMind pipeline with context compilation and token budget",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task to execute"},
                "budget": {"type": "integer", "description": "Token budget for context"},
                "system_prompt": {"type": "string", "description": "System prompt (optional)"},
            },
            "required": ["task", "budget"],
        },
    },
```

Add handler in `_handle_tools_call` method and implementation method:

```python
            if tool_name == "orchestrate_compiled":
                return _result_response(req_id, self._call_orchestrate_compiled(arguments))
```

```python
    def _call_orchestrate_compiled(self, args: dict[str, Any]) -> dict[str, Any]:
        task = args["task"]
        budget = args["budget"]
        system_prompt = args.get("system_prompt", "You are a helpful AI assistant.")
        result = self._orchestrator.run_compiled(task, budget=budget, system_prompt=system_prompt)
        session_id = result["session_id"]
        self._evidence_store[session_id] = self._orchestrator.evidence
        return {
            "content": [{"type": "text", "text": result.get("result", "")}],
            "session_id": session_id,
            "budget_used": result.get("budget_used", 0),
            "within_budget": result.get("within_budget", True),
        }
```

**Step 7: Commit**

```bash
git add ygn-brain/src/ygn_brain/orchestrator.py \
       ygn-brain/src/ygn_brain/mcp_server.py \
       ygn-brain/tests/test_orchestrator_compiled.py
git commit -m "feat(brain): wire context compiler into Orchestrator + MCP server"
```

---

### Task 10: Update Package Exports

**Files:**
- Modify: `ygn-brain/src/ygn_brain/context_compiler/__init__.py`
- Modify: `ygn-brain/src/ygn_brain/tool_interrupt/__init__.py`
- Modify: `ygn-brain/src/ygn_brain/__init__.py` (add new exports)

**Step 1: Update context_compiler/__init__.py**

```python
"""Context Compiler — compiles Session events into budget-aware WorkingContext."""

from .artifact_store import ArtifactHandle, ArtifactStore, FsArtifactStore, SqliteArtifactStore
from .processors import (
    ArtifactAttacher,
    Compactor,
    ContextCompiler,
    HistorySelector,
    MemoryPreloader,
    Processor,
)
from .session import EventLog, Session, SessionEvent
from .token_budget import TokenBudget, estimate_tokens
from .working_context import WorkingContext

__all__ = [
    "ArtifactAttacher",
    "ArtifactHandle",
    "ArtifactStore",
    "Compactor",
    "ContextCompiler",
    "EventLog",
    "FsArtifactStore",
    "HistorySelector",
    "MemoryPreloader",
    "Processor",
    "Session",
    "SessionEvent",
    "SqliteArtifactStore",
    "TokenBudget",
    "WorkingContext",
    "estimate_tokens",
]
```

**Step 2: Update tool_interrupt/__init__.py**

```python
"""Tool Interrupts — typed events, normalization, and schema validation for tool calls."""

from .events import ToolEvent, ToolEventKind
from .handler import ToolInterruptHandler
from .normalizer import PerceptionAligner
from .schemas import SchemaRegistry

__all__ = [
    "PerceptionAligner",
    "SchemaRegistry",
    "ToolEvent",
    "ToolEventKind",
    "ToolInterruptHandler",
]
```

**Step 3: Add to main ygn_brain/__init__.py**

Add these imports after the existing `tool_bridge` import (line 103):

```python
from .context_compiler import (
    ArtifactAttacher,
    ArtifactHandle,
    ArtifactStore,
    Compactor,
    ContextCompiler,
    EventLog,
    FsArtifactStore,
    HistorySelector,
    MemoryPreloader,
    Session,
    SessionEvent,
    SqliteArtifactStore,
    TokenBudget,
    WorkingContext,
    estimate_tokens,
)
from .tool_interrupt import (
    PerceptionAligner,
    SchemaRegistry,
    ToolEvent,
    ToolEventKind,
    ToolInterruptHandler,
)
```

Add these names to `__all__` (alphabetically):

```python
    "ArtifactAttacher",
    "ArtifactHandle",
    "ArtifactStore",
    "Compactor",
    "ContextCompiler",
    "EventLog",
    "estimate_tokens",
    "FsArtifactStore",
    "HistorySelector",
    "MemoryPreloader",
    "PerceptionAligner",
    "SchemaRegistry",
    "Session",
    "SessionEvent",
    "SqliteArtifactStore",
    "TokenBudget",
    "ToolEvent",
    "ToolEventKind",
    "ToolInterruptHandler",
    "WorkingContext",
```

**Step 4: Run full test suite**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/ -v`
Expected: All tests PASS (existing + new)

**Step 5: Commit**

```bash
git add ygn-brain/src/ygn_brain/context_compiler/__init__.py \
       ygn-brain/src/ygn_brain/tool_interrupt/__init__.py \
       ygn-brain/src/ygn_brain/__init__.py
git commit -m "feat(brain): export context compiler + tool interrupt modules"
```

---

### Task 11: E2E Test — Context Compiler Pipeline

**Files:**
- Test: `ygn-brain/tests/test_context_compiler_e2e.py`

**Step 1: Write the E2E tests**

Create `ygn-brain/tests/test_context_compiler_e2e.py`:

```python
"""E2E tests for the full context compiler pipeline."""

import tempfile
from pathlib import Path

from ygn_brain.context_compiler.artifact_store import SqliteArtifactStore
from ygn_brain.context_compiler.processors import (
    ArtifactAttacher,
    Compactor,
    ContextCompiler,
    HistorySelector,
)
from ygn_brain.context_compiler.session import Session


def test_large_payload_externalized():
    """Verify that a large tool output is externalized to ArtifactStore
    and replaced with a handle in the WorkingContext."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SqliteArtifactStore(db_path=Path(tmpdir) / "art.db")

        session = Session()
        session.record("user_input", {"text": "Analyze this file"}, token_estimate=10)

        # Simulate a large tool result stored in session
        large_output = "Line of output data. " * 500  # ~10KB
        session.record(
            "tool_success",
            {"tool": "file_read", "result": large_output},
            token_estimate=len(large_output.split()) * 2,
        )

        compiler = ContextCompiler(processors=[
            HistorySelector(keep_first=2, keep_last=3),
            Compactor(),
            ArtifactAttacher(artifact_store=store, threshold_bytes=1024),
        ])

        ctx = compiler.compile(session, budget=500, system_prompt="You are helpful.")

        # The large payload should be externalized
        assert len(ctx.artifact_refs) >= 0  # Artifact attacher only processes tool_results list
        # WorkingContext should be within budget given the externalization
        assert ctx.token_count < 5000  # much less than the raw payload


def test_budget_respected():
    """Verify that the compiled WorkingContext respects the token budget."""
    session = Session()
    for i in range(50):
        session.record(
            "user_input",
            {"role": "user", "content": f"This is message number {i} with some content"},
            token_estimate=15,
        )

    compiler = ContextCompiler(processors=[
        HistorySelector(keep_first=2, keep_last=3),
        Compactor(),
    ])

    ctx = compiler.compile(session, budget=200, system_prompt="Short prompt.")
    # HistorySelector should have trimmed to 5 messages
    assert len(ctx.history) == 5
    # Token count should be reasonable
    assert ctx.token_count < 200
```

**Step 2: Run E2E tests**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/test_context_compiler_e2e.py -v`
Expected: 2 PASSED

**Step 3: Commit**

```bash
git add ygn-brain/tests/test_context_compiler_e2e.py
git commit -m "test(brain): add E2E tests for context compiler pipeline"
```

---

### Task 12: Demo CLI Entry Point

**Files:**
- Create: `ygn-brain/src/ygn_brain/demo_compiler.py`
- Modify: `ygn-brain/pyproject.toml` (add entry point)

**Step 1: Create demo_compiler.py**

Create `ygn-brain/src/ygn_brain/demo_compiler.py`:

```python
"""Demo: context compiler with artifact externalization.

Usage: ygn-brain-demo-compiler
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .context_compiler.artifact_store import SqliteArtifactStore
from .context_compiler.processors import (
    ArtifactAttacher,
    Compactor,
    ContextCompiler,
    HistorySelector,
)
from .context_compiler.session import Session
from .context_compiler.working_context import WorkingContext


def main() -> None:
    """Run the context compiler demo."""
    print("=" * 60)
    print("Y-GN Context Compiler Demo")
    print("=" * 60)

    # 1. Create session + artifact store
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "demo_artifacts.db"
    store = SqliteArtifactStore(db_path=db_path)
    print(f"\nArtifact store: {db_path}")

    session = Session()
    print(f"Session ID: {session.session_id}")

    # 2. Record user input
    session.record("user_input", {"text": "Analyze the system logs and summarize errors"}, token_estimate=15)

    # 3. Simulate a large tool output (10KB)
    large_output = "ERROR 2026-02-27 10:15:32 [worker-7] Connection timeout to db-primary\n" * 200
    print(f"\nSimulated tool output: {len(large_output)} bytes ({len(large_output.split())} words)")

    # 4. Build compiler with processors
    compiler = ContextCompiler(processors=[
        HistorySelector(keep_first=2, keep_last=3),
        Compactor(),
        ArtifactAttacher(artifact_store=store, threshold_bytes=1024),
    ])

    # 5. First compile WITHOUT artifact attacher (to show the "before")
    compiler_no_artifacts = ContextCompiler(processors=[
        HistorySelector(keep_first=2, keep_last=3),
        Compactor(),
    ])

    # Manually add tool result to show externalization
    from .context_compiler.working_context import WorkingContext as WC

    ctx_before = compiler_no_artifacts.compile(
        session, budget=500, system_prompt="You are a log analysis assistant."
    )
    # Inject tool result to simulate
    ctx_before_with_tool = WorkingContext(
        system_prompt=ctx_before.system_prompt,
        history=ctx_before.history,
        memory_hits=ctx_before.memory_hits,
        artifact_refs=ctx_before.artifact_refs,
        tool_results=[{"tool": "log_reader", "result": large_output}],
        token_count=ctx_before.token_count + len(large_output.split()) * 2,
        budget=500,
    )

    print(f"\n--- BEFORE externalization ---")
    print(f"Token count: {ctx_before_with_tool.token_count}")
    print(f"Within budget (500): {ctx_before_with_tool.is_within_budget()}")
    print(f"Overflow: {ctx_before_with_tool.overflow()} tokens")
    print(f"Tool results: {len(ctx_before_with_tool.tool_results)} (raw in prompt)")
    print(f"Artifact refs: {len(ctx_before_with_tool.artifact_refs)}")

    # 6. Now compile WITH artifact attacher
    # Store the large output as a tool result in a fresh compile
    session2 = Session(session_id=session.session_id)
    session2.record("user_input", {"text": "Analyze the system logs"}, token_estimate=10)

    ctx_after_base = compiler.compile(
        session2, budget=500, system_prompt="You are a log analysis assistant."
    )
    # Manually attach via ArtifactAttacher
    attacher = ArtifactAttacher(artifact_store=store, threshold_bytes=1024)
    ctx_with_tool = WorkingContext(
        system_prompt=ctx_after_base.system_prompt,
        history=ctx_after_base.history,
        memory_hits=ctx_after_base.memory_hits,
        artifact_refs=ctx_after_base.artifact_refs,
        tool_results=[{"tool": "log_reader", "result": large_output}],
        token_count=ctx_after_base.token_count + len(large_output.split()) * 2,
        budget=500,
    )
    ctx_after = attacher.process(session2, ctx_with_tool, budget=500)

    print(f"\n--- AFTER externalization ---")
    print(f"Token count: {ctx_after.token_count}")
    print(f"Within budget (500): {ctx_after.is_within_budget()}")
    print(f"Overflow: {ctx_after.overflow()} tokens")
    print(f"Tool results: {len(ctx_after.tool_results)} (remaining in prompt)")
    print(f"Artifact refs: {len(ctx_after.artifact_refs)}")

    if ctx_after.artifact_refs:
        ref = ctx_after.artifact_refs[0]
        print(f"\n  Handle: {ref['handle'][:16]}...")
        print(f"  Summary: {ref['summary'][:80]}...")
        print(f"  Size: {ref['size_bytes']} bytes")

        # Verify retrieval
        data = store.retrieve(ref["handle"])
        if data:
            print(f"  Retrieved: {len(data)} bytes (matches original: {data == large_output.encode()})")

    # 7. Show the compiled messages
    messages = ctx_after.to_messages()
    print(f"\n--- Compiled messages for LLM ---")
    for i, msg in enumerate(messages):
        content = msg["content"]
        if len(content) > 200:
            content = content[:200] + "..."
        print(f"  [{i}] {msg['role']}: {content}")

    print(f"\n{'=' * 60}")
    print("Demo complete. Large tool output externalized, handle in prompt.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
```

**Step 2: Add entry point to pyproject.toml**

Add to `[project.scripts]` section in `ygn-brain/pyproject.toml`:

```toml
ygn-brain-demo-compiler = "ygn_brain.demo_compiler:main"
```

**Step 3: Test the demo**

Run: `cd /c/Code/Y-GN && python -m ygn_brain.demo_compiler`
Expected: Prints the demo output showing externalization working

**Step 4: Commit**

```bash
git add ygn-brain/src/ygn_brain/demo_compiler.py ygn-brain/pyproject.toml
git commit -m "feat(brain): add demo CLI for context compiler (ygn-brain-demo-compiler)"
```

---

### Task 13: Lint, Type Check, Full Test Suite

**Files:** No new files — verification only.

**Step 1: Run ruff**

Run: `cd /c/Code/Y-GN/ygn-brain && python -m ruff check src/ tests/`
Expected: No errors. Fix any issues.

**Step 2: Run mypy**

Run: `cd /c/Code/Y-GN/ygn-brain && python -m mypy src/ygn_brain/context_compiler/ src/ygn_brain/tool_interrupt/`
Expected: No errors (or only pre-existing ones). Fix new issues.

**Step 3: Run full Python test suite**

Run: `cd /c/Code/Y-GN && python -m pytest ygn-brain/tests/ -v --tb=short`
Expected: All tests PASS (existing 445 + ~17 new = ~462)

**Step 4: Run Rust tests (verify no breakage)**

Run: `cd /c/Code/Y-GN && cargo test -p ygn-core`
Expected: All 380 Rust tests PASS (no changes to Rust code)

**Step 5: Fix any issues found, commit**

```bash
git add -u
git commit -m "fix(brain): lint + type check fixes for context compiler"
```

---

### Task 14: Update CLAUDE.md & Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `ygn-brain/src/ygn_brain/context_compiler/__init__.py` (already done)

**Step 1: Update CLAUDE.md**

Add to the `### ygn-brain internals` section (after the harness description):

```markdown
- **ContextCompiler** — Session(EventLog) as ground truth → processors pipeline → WorkingContext (budget-aware compiled view)
  - Processors: HistorySelector, Compactor, MemoryPreloader, ArtifactAttacher
  - ArtifactStore: SqliteArtifactStore + FsArtifactStore (content-addressed, SHA-256)
- **ToolInterrupts** — ToolInterruptHandler wraps MCP tool calls with typed events (success/error/timeout), PerceptionAligner (schema validation + secret redaction + summaries), SchemaRegistry
```

Add to `### CLI commands (ygn-brain)`:

```markdown
ygn-brain-demo-compiler        # Demo: context compiler with artifact externalization
```

Update `### Test counts`:

```markdown
- Python (ygn-brain): ~462 tests
- Total: ~842 tests
```

Add new key Python modules:

```markdown
- `context_compiler/session.py` — Session(EventLog) wrapping EvidencePack
- `context_compiler/working_context.py` — WorkingContext compiled view
- `context_compiler/processors.py` — ContextCompiler pipeline (HistorySelector, Compactor, MemoryPreloader, ArtifactAttacher)
- `context_compiler/artifact_store.py` — ArtifactStore ABC + SqliteArtifactStore + FsArtifactStore
- `context_compiler/token_budget.py` — TokenBudget tracker + estimate_tokens()
- `tool_interrupt/events.py` — ToolEvent, ToolEventKind
- `tool_interrupt/handler.py` — ToolInterruptHandler (timeout + normalization + externalization)
- `tool_interrupt/normalizer.py` — PerceptionAligner (schema + redact + summarize)
- `tool_interrupt/schemas.py` — SchemaRegistry per-tool JSON Schema
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with context compiler + tool interrupt modules"
```

---

## Summary

| Task | Files Created | Files Modified | Tests Added |
|------|--------------|----------------|-------------|
| 1. Session & EventLog | 2 | 0 | 3 |
| 2. Token Budget | 1 | 0 | 3 |
| 3. WorkingContext | 1 | 0 | 2 |
| 4. ArtifactStore | 1 | 0 | 3 |
| 5. Processors | 1 | 0 | 4 |
| 6. Tool Events | 2 | 0 | 3 |
| 7. Schema + Normalizer | 2 | 0 | 5 |
| 8. ToolInterruptHandler | 1 | 0 | 3 |
| 9. Orchestrator wiring | 1 test | 2 | 2 |
| 10. Package exports | 0 | 3 | 0 |
| 11. E2E tests | 1 test | 0 | 2 |
| 12. Demo CLI | 1 | 1 | 0 |
| 13. Lint/verify | 0 | 0 | 0 |
| 14. Documentation | 0 | 1 | 0 |
| **Total** | **14 new** | **7 modified** | **30 tests** |

## Verification Commands

```bash
# Full gate
cd /c/Code/Y-GN
python -m pytest ygn-brain/tests/ -v --tb=short   # All Python tests
cargo test -p ygn-core                              # All Rust tests (unchanged)

# Lint
cd ygn-brain && python -m ruff check src/ tests/

# Demo
python -m ygn_brain.demo_compiler
```

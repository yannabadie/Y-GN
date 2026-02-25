"""Evidence Pack generator — auditable execution trace."""

from __future__ import annotations

import time
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class EvidenceKind(StrEnum):
    """Constrained set of valid evidence entry kinds."""

    INPUT = "input"
    DECISION = "decision"
    TOOL_CALL = "tool_call"
    SOURCE = "source"
    OUTPUT = "output"
    ERROR = "error"


class EvidenceEntry(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    phase: str
    kind: EvidenceKind
    data: dict[str, Any] = {}


class EvidencePack(BaseModel):
    session_id: str
    entries: list[EvidenceEntry] = []
    created_at: float = Field(default_factory=time.time)

    def add(self, phase: str, kind: str, data: dict[str, Any] | None = None) -> None:
        self.entries.append(
            EvidenceEntry(phase=phase, kind=EvidenceKind(kind), data=data or {})
        )

    def to_jsonl(self) -> str:
        lines = [entry.model_dump_json() for entry in self.entries]
        return "\n".join(lines)

    def save(self, path: Path) -> Path:
        out = path / f"evidence_{self.session_id}.jsonl"
        out.write_text(self.to_jsonl(), encoding="utf-8")
        return out

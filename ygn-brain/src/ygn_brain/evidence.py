"""Evidence Pack generator — auditable execution trace.

Supports SHA-256 hash chain, ed25519 signing, and RFC 6962 Merkle tree
for tamper-evident audit trails (EU AI Act Art. 12 compliance).
"""

from __future__ import annotations

import hashlib
import json
import time
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EvidenceKind(StrEnum):
    """Constrained set of valid evidence entry kinds."""

    INPUT = "input"
    DECISION = "decision"
    TOOL_CALL = "tool_call"
    SOURCE = "source"
    OUTPUT = "output"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_entry_id() -> str:
    """Generate a time-sortable entry ID (UUIDv7-like fallback)."""
    return f"{int(time.time() * 1000):012x}-{uuid4().hex[:20]}"


def _compute_entry_hash(
    timestamp: float, phase: str, kind: str, data: dict[str, Any], prev_hash: str
) -> str:
    """SHA-256 of canonical JSON representation of entry fields."""
    canonical = json.dumps(
        {
            "data": data,
            "kind": kind,
            "phase": phase,
            "prev_hash": prev_hash,
            "timestamp": timestamp,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _merkle_root(leaves: list[bytes]) -> bytes:
    """RFC 6962 Merkle tree hash computation."""
    if len(leaves) == 0:
        return hashlib.sha256(b"").digest()
    if len(leaves) == 1:
        return hashlib.sha256(b"\x00" + leaves[0]).digest()
    # k = largest power of 2 less than n
    k = 1
    while k * 2 < len(leaves):
        k *= 2
    left = _merkle_root(leaves[:k])
    right = _merkle_root(leaves[k:])
    return hashlib.sha256(b"\x01" + left + right).digest()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class EvidenceEntry(BaseModel):
    entry_id: str = Field(default_factory=_generate_entry_id)
    timestamp: float = Field(default_factory=time.time)
    phase: str
    kind: EvidenceKind
    data: dict[str, Any] = {}
    prev_hash: str = ""
    entry_hash: str = ""
    signature: str = ""


class EvidencePack(BaseModel):
    session_id: str
    entries: list[EvidenceEntry] = []
    created_at: float = Field(default_factory=time.time)
    # EU AI Act Art. 12 fields
    start_time: float = 0.0
    end_time: float = 0.0
    model_id: str = ""
    signer_public_key: str = ""
    merkle_root: str = ""

    def add(self, phase: str, kind: str, data: dict[str, Any] | None = None) -> None:
        prev_hash = self.entries[-1].entry_hash if self.entries else ""
        entry = EvidenceEntry(
            phase=phase, kind=EvidenceKind(kind), data=data or {}, prev_hash=prev_hash
        )
        entry.entry_hash = _compute_entry_hash(
            entry.timestamp, entry.phase, entry.kind.value, entry.data, entry.prev_hash
        )
        now = entry.timestamp
        if self.start_time == 0.0:
            self.start_time = now
        self.end_time = now
        self.entries.append(entry)

    def sign(self, private_key_hex: str) -> None:
        """Sign all entries with ed25519. Sets signer_public_key."""
        from nacl.signing import SigningKey  # noqa: S404

        seed = bytes.fromhex(private_key_hex)
        signing_key = SigningKey(seed)
        self.signer_public_key = signing_key.verify_key.encode().hex()
        for entry in self.entries:
            sig = signing_key.sign(entry.entry_hash.encode())
            entry.signature = sig.signature.hex()

    def verify(self, public_key_hex: str | None = None) -> bool:
        """Verify hash chain integrity and optionally signatures.

        Returns True for unsigned packs (chain-only verification).
        """
        for i, entry in enumerate(self.entries):
            if not entry.entry_hash:
                continue
            expected_prev = self.entries[i - 1].entry_hash if i > 0 else ""
            if entry.prev_hash != expected_prev:
                return False
            expected_hash = _compute_entry_hash(
                entry.timestamp, entry.phase, entry.kind.value, entry.data, entry.prev_hash
            )
            if entry.entry_hash != expected_hash:
                return False

        pk_hex = public_key_hex or self.signer_public_key
        has_signatures = any(e.signature for e in self.entries)
        if pk_hex and has_signatures:
            from nacl.exceptions import BadSignatureError
            from nacl.signing import VerifyKey

            verify_key = VerifyKey(bytes.fromhex(pk_hex))
            for entry in self.entries:
                if not entry.signature:
                    return False
                try:
                    verify_key.verify(
                        entry.entry_hash.encode(), bytes.fromhex(entry.signature)
                    )
                except BadSignatureError:
                    return False

        return True

    def merkle_root_hash(self) -> str:
        """Compute RFC 6962 Merkle tree root of entry hashes."""
        if not self.entries:
            return hashlib.sha256(b"").hexdigest()
        leaves = [bytes.fromhex(e.entry_hash) for e in self.entries if e.entry_hash]
        if not leaves:
            return hashlib.sha256(b"").hexdigest()
        return _merkle_root(leaves).hex()

    def to_jsonl(self) -> str:
        lines = [entry.model_dump_json() for entry in self.entries]
        return "\n".join(lines)

    def save(self, path: Path) -> Path:
        self.merkle_root = self.merkle_root_hash()
        out = path / f"evidence_{self.session_id}.jsonl"
        out.write_text(self.to_jsonl(), encoding="utf-8")
        return out

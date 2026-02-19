"""Micro Agent Communication Protocol (uACP) codec.

A transport-agnostic binary codec with compact framing for edge-constrained
multi-agent communication. Supports four verbs: PING, TELL, ASK, OBSERVE.

Wire format (big-endian)::

    [1B verb][4B message_id][8B timestamp]
    [2B sender_len][sender_bytes][4B payload_len][payload_bytes]

Total header overhead: 19 bytes + sender_len + payload_len
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from enum import StrEnum
from itertools import count

# ---------------------------------------------------------------------------
# Verb
# ---------------------------------------------------------------------------

_msg_id_counter = count(1)


class UacpVerb(StrEnum):
    """The four uACP verbs."""

    PING = "ping"
    TELL = "tell"
    ASK = "ask"
    OBSERVE = "observe"


# Mapping between enum values and wire bytes.
_VERB_TO_BYTE: dict[UacpVerb, int] = {
    UacpVerb.PING: 0x01,
    UacpVerb.TELL: 0x02,
    UacpVerb.ASK: 0x03,
    UacpVerb.OBSERVE: 0x04,
}

_BYTE_TO_VERB: dict[int, UacpVerb] = {v: k for k, v in _VERB_TO_BYTE.items()}

# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

# Minimum header: 1 (verb) + 4 (msg_id) + 8 (ts) + 2 (sender_len) + 4 (payload_len) = 19
_MIN_HEADER_SIZE = 19


@dataclass
class UacpMessage:
    """A single uACP message."""

    verb: UacpVerb
    message_id: int
    sender_id: str
    payload: bytes
    timestamp: int

    # -- helper constructors ------------------------------------------------

    @classmethod
    def ping(cls, sender: str) -> UacpMessage:
        """Create a PING message (no payload)."""
        return cls(
            verb=UacpVerb.PING,
            message_id=next(_msg_id_counter),
            sender_id=sender,
            payload=b"",
            timestamp=_now_millis(),
        )

    @classmethod
    def tell(cls, sender: str, payload: bytes) -> UacpMessage:
        """Create a TELL message."""
        return cls(
            verb=UacpVerb.TELL,
            message_id=next(_msg_id_counter),
            sender_id=sender,
            payload=payload,
            timestamp=_now_millis(),
        )

    @classmethod
    def ask(cls, sender: str, payload: bytes) -> UacpMessage:
        """Create an ASK message."""
        return cls(
            verb=UacpVerb.ASK,
            message_id=next(_msg_id_counter),
            sender_id=sender,
            payload=payload,
            timestamp=_now_millis(),
        )

    @classmethod
    def observe(cls, sender: str, payload: bytes) -> UacpMessage:
        """Create an OBSERVE message."""
        return cls(
            verb=UacpVerb.OBSERVE,
            message_id=next(_msg_id_counter),
            sender_id=sender,
            payload=payload,
            timestamp=_now_millis(),
        )


def _now_millis() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Codec
# ---------------------------------------------------------------------------


class UacpCodec:
    """Encodes and decodes ``UacpMessage`` values to/from the compact binary wire format."""

    @staticmethod
    def encode(msg: UacpMessage) -> bytes:
        """Serialize a single message to the binary wire format."""
        sender_bytes = msg.sender_id.encode("utf-8")
        header = struct.pack(
            ">BIQ",
            _VERB_TO_BYTE[msg.verb],
            msg.message_id,
            msg.timestamp,
        )
        sender_hdr = struct.pack(">H", len(sender_bytes))
        payload_hdr = struct.pack(">I", len(msg.payload))
        return header + sender_hdr + sender_bytes + payload_hdr + msg.payload

    @staticmethod
    def decode(data: bytes | bytearray | memoryview) -> UacpMessage:
        """Deserialize a single message from the binary wire format."""
        raw = bytes(data)
        if len(raw) < _MIN_HEADER_SIZE:
            msg = f"uACP frame too short: {len(raw)} bytes (minimum {_MIN_HEADER_SIZE})"
            raise ValueError(msg)

        pos = 0

        # verb
        verb_byte = raw[pos]
        if verb_byte not in _BYTE_TO_VERB:
            msg = f"invalid uACP verb byte: 0x{verb_byte:02x}"
            raise ValueError(msg)
        verb = _BYTE_TO_VERB[verb_byte]
        pos += 1

        # message_id + timestamp
        (message_id, timestamp) = struct.unpack_from(">IQ", raw, pos)
        pos += 12

        # sender
        (sender_len,) = struct.unpack_from(">H", raw, pos)
        pos += 2

        if pos + sender_len > len(raw):
            msg = f"uACP sender_len ({sender_len}) exceeds remaining data ({len(raw) - pos})"
            raise ValueError(msg)

        sender_raw = raw[pos : pos + sender_len]
        try:
            sender_id = sender_raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            msg = "uACP sender_id is not valid UTF-8"
            raise ValueError(msg) from exc
        pos += sender_len

        # payload
        if pos + 4 > len(raw):
            msg = "uACP frame truncated: missing payload_len"
            raise ValueError(msg)

        (payload_len,) = struct.unpack_from(">I", raw, pos)
        pos += 4

        if pos + payload_len > len(raw):
            msg = f"uACP payload_len ({payload_len}) exceeds remaining data ({len(raw) - pos})"
            raise ValueError(msg)

        payload = raw[pos : pos + payload_len]

        return UacpMessage(
            verb=verb,
            message_id=message_id,
            sender_id=sender_id,
            payload=payload,
            timestamp=timestamp,
        )

    @staticmethod
    def encode_batch(msgs: list[UacpMessage]) -> bytes:
        """Encode multiple messages into a single buffer (concatenated frames)."""
        return b"".join(UacpCodec.encode(m) for m in msgs)

    @staticmethod
    def decode_batch(data: bytes | bytearray | memoryview) -> list[UacpMessage]:
        """Decode all messages from a concatenated buffer."""
        raw = bytes(data)
        msgs: list[UacpMessage] = []
        pos = 0

        while pos < len(raw):
            if pos + _MIN_HEADER_SIZE > len(raw):
                msg = f"uACP batch: trailing {len(raw) - pos} bytes too short for a header"
                raise ValueError(msg)

            # Peek at sender_len to compute frame size.
            (sender_len,) = struct.unpack_from(">H", raw, pos + 13)
            pl_off = pos + 15 + sender_len
            if pl_off + 4 > len(raw):
                msg = "uACP batch: frame truncated at payload_len"
                raise ValueError(msg)
            (payload_len,) = struct.unpack_from(">I", raw, pl_off)

            frame_len = _MIN_HEADER_SIZE + sender_len + payload_len
            if pos + frame_len > len(raw):
                msg = "uACP batch: frame overflows buffer"
                raise ValueError(msg)

            msgs.append(UacpCodec.decode(raw[pos : pos + frame_len]))
            pos += frame_len

        return msgs

"""Tests for the uACP codec."""

from __future__ import annotations

import pytest

from ygn_brain.uacp import UacpCodec, UacpMessage, UacpVerb

# Cross-language interop test vector.
# verb=PING, message_id=42, sender_id="node-1", timestamp=1700000000000, payload=b""
# Expected hex: 010000002a0000018bca83d60000066e6f64652d3100000000
INTEROP_HEX = "010000002a0000018bcfe5680000066e6f64652d3100000000"


def _make_test_message(verb: UacpVerb, payload: bytes = b"") -> UacpMessage:
    return UacpMessage(
        verb=verb,
        message_id=1,
        sender_id="test-agent",
        payload=payload,
        timestamp=1_700_000_000_000,
    )


class TestRoundtrip:
    """Encode/decode roundtrip for each verb."""

    def test_roundtrip_ping(self) -> None:
        msg = _make_test_message(UacpVerb.PING)
        decoded = UacpCodec.decode(UacpCodec.encode(msg))
        assert decoded.verb == UacpVerb.PING
        assert decoded.message_id == msg.message_id
        assert decoded.sender_id == msg.sender_id
        assert decoded.payload == msg.payload
        assert decoded.timestamp == msg.timestamp

    def test_roundtrip_tell(self) -> None:
        msg = _make_test_message(UacpVerb.TELL, b"hello world")
        decoded = UacpCodec.decode(UacpCodec.encode(msg))
        assert decoded.verb == UacpVerb.TELL
        assert decoded.payload == b"hello world"

    def test_roundtrip_ask(self) -> None:
        msg = _make_test_message(UacpVerb.ASK, b"question?")
        decoded = UacpCodec.decode(UacpCodec.encode(msg))
        assert decoded.verb == UacpVerb.ASK
        assert decoded.payload == b"question?"

    def test_roundtrip_observe(self) -> None:
        msg = _make_test_message(UacpVerb.OBSERVE, b"metric=42")
        decoded = UacpCodec.decode(UacpCodec.encode(msg))
        assert decoded.verb == UacpVerb.OBSERVE
        assert decoded.payload == b"metric=42"


class TestEdgeCases:
    """Edge cases: empty payload, large payload."""

    def test_empty_payload(self) -> None:
        msg = _make_test_message(UacpVerb.TELL, b"")
        decoded = UacpCodec.decode(UacpCodec.encode(msg))
        assert decoded.payload == b""

    def test_large_payload(self) -> None:
        payload = bytes([0xAB] * 1_000_000)  # 1 MB
        msg = _make_test_message(UacpVerb.TELL, payload)
        decoded = UacpCodec.decode(UacpCodec.encode(msg))
        assert len(decoded.payload) == 1_000_000
        assert decoded.payload == payload


class TestBatch:
    """Batch encode/decode."""

    def test_batch_roundtrip(self) -> None:
        msgs = [
            _make_test_message(UacpVerb.PING),
            _make_test_message(UacpVerb.TELL, b"data"),
            _make_test_message(UacpVerb.ASK, b"q"),
        ]
        encoded = UacpCodec.encode_batch(msgs)
        decoded = UacpCodec.decode_batch(encoded)
        assert len(decoded) == 3
        assert decoded[0].verb == UacpVerb.PING
        assert decoded[1].verb == UacpVerb.TELL
        assert decoded[2].verb == UacpVerb.ASK
        assert decoded[1].payload == b"data"

    def test_encode_batch_decode_batch_roundtrip(self) -> None:
        msgs = [
            UacpMessage(
                verb=UacpVerb.TELL,
                message_id=i,
                sender_id=f"agent-{i}",
                payload=f"payload-{i}".encode(),
                timestamp=1_700_000_000_000 + i,
            )
            for i in range(5)
        ]
        decoded = UacpCodec.decode_batch(UacpCodec.encode_batch(msgs))
        assert len(decoded) == 5
        for i, m in enumerate(decoded):
            assert m.message_id == i
            assert m.sender_id == f"agent-{i}"
            assert m.payload == f"payload-{i}".encode()


class TestErrors:
    """Decode error handling."""

    def test_invalid_verb(self) -> None:
        data = bytearray(UacpCodec.encode(_make_test_message(UacpVerb.PING)))
        data[0] = 0xFF
        with pytest.raises(ValueError, match="invalid uACP verb byte"):
            UacpCodec.decode(bytes(data))

    def test_truncated_data(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            UacpCodec.decode(b"\x01\x00")

    def test_invalid_utf8_sender(self) -> None:
        data = bytearray(UacpCodec.encode(_make_test_message(UacpVerb.PING)))
        # sender starts at offset 15 (1+4+8+2)
        data[15] = 0xFF
        data[16] = 0xFE
        with pytest.raises(ValueError, match="UTF-8"):
            UacpCodec.decode(bytes(data))


class TestInterop:
    """Cross-language interop test vector."""

    def test_interop_encode(self) -> None:
        msg = UacpMessage(
            verb=UacpVerb.PING,
            message_id=42,
            sender_id="node-1",
            payload=b"",
            timestamp=1_700_000_000_000,
        )
        encoded = UacpCodec.encode(msg)
        assert encoded.hex() == INTEROP_HEX

    def test_interop_decode(self) -> None:
        raw = bytes.fromhex(INTEROP_HEX)
        decoded = UacpCodec.decode(raw)
        assert decoded.verb == UacpVerb.PING
        assert decoded.message_id == 42
        assert decoded.sender_id == "node-1"
        assert decoded.payload == b""
        assert decoded.timestamp == 1_700_000_000_000


class TestConstructors:
    """Helper constructors produce valid messages."""

    def test_ping_constructor(self) -> None:
        msg = UacpMessage.ping("node-a")
        assert msg.verb == UacpVerb.PING
        assert msg.sender_id == "node-a"
        assert msg.payload == b""

    def test_tell_constructor(self) -> None:
        msg = UacpMessage.tell("node-b", b"data")
        assert msg.verb == UacpVerb.TELL
        assert msg.payload == b"data"

    def test_ask_constructor(self) -> None:
        msg = UacpMessage.ask("node-c", b"q")
        assert msg.verb == UacpVerb.ASK
        assert msg.payload == b"q"

    def test_observe_constructor(self) -> None:
        msg = UacpMessage.observe("node-d", b"obs")
        assert msg.verb == UacpVerb.OBSERVE
        assert msg.payload == b"obs"

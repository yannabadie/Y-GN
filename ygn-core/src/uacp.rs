//! Micro Agent Communication Protocol (uACP) codec.
//!
//! A transport-agnostic binary codec with compact framing for edge-constrained
//! multi-agent communication. Supports four verbs: PING, TELL, ASK, OBSERVE.
//!
//! Wire format (big-endian):
//! ```text
//! [1B verb][4B message_id][8B timestamp][2B sender_len][sender_bytes][4B payload_len][payload_bytes]
//! ```
//! Total header overhead: 19 bytes + sender_len + payload_len

use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU32, Ordering};

// ---------------------------------------------------------------------------
// Verb
// ---------------------------------------------------------------------------

/// The four uACP verbs.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum UacpVerb {
    Ping = 0x01,
    Tell = 0x02,
    Ask = 0x03,
    Observe = 0x04,
}

impl UacpVerb {
    /// Convert a raw byte to a verb, returning an error for unknown values.
    fn from_byte(b: u8) -> anyhow::Result<Self> {
        match b {
            0x01 => Ok(Self::Ping),
            0x02 => Ok(Self::Tell),
            0x03 => Ok(Self::Ask),
            0x04 => Ok(Self::Observe),
            other => anyhow::bail!("invalid uACP verb byte: 0x{other:02x}"),
        }
    }
}

// ---------------------------------------------------------------------------
// Message
// ---------------------------------------------------------------------------

/// A single uACP message.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UacpMessage {
    pub verb: UacpVerb,
    pub message_id: u32,
    pub sender_id: String,
    pub payload: Vec<u8>,
    pub timestamp: u64,
}

/// Global atomic counter for generating unique message IDs.
static MSG_ID_COUNTER: AtomicU32 = AtomicU32::new(1);

impl UacpMessage {
    /// Create a PING message (no payload).
    pub fn ping(sender: &str) -> Self {
        Self {
            verb: UacpVerb::Ping,
            message_id: MSG_ID_COUNTER.fetch_add(1, Ordering::Relaxed),
            sender_id: sender.to_string(),
            payload: Vec::new(),
            timestamp: now_millis(),
        }
    }

    /// Create a TELL message.
    pub fn tell(sender: &str, payload: &[u8]) -> Self {
        Self {
            verb: UacpVerb::Tell,
            message_id: MSG_ID_COUNTER.fetch_add(1, Ordering::Relaxed),
            sender_id: sender.to_string(),
            payload: payload.to_vec(),
            timestamp: now_millis(),
        }
    }

    /// Create an ASK message.
    pub fn ask(sender: &str, payload: &[u8]) -> Self {
        Self {
            verb: UacpVerb::Ask,
            message_id: MSG_ID_COUNTER.fetch_add(1, Ordering::Relaxed),
            sender_id: sender.to_string(),
            payload: payload.to_vec(),
            timestamp: now_millis(),
        }
    }

    /// Create an OBSERVE message.
    pub fn observe(sender: &str, payload: &[u8]) -> Self {
        Self {
            verb: UacpVerb::Observe,
            message_id: MSG_ID_COUNTER.fetch_add(1, Ordering::Relaxed),
            sender_id: sender.to_string(),
            payload: payload.to_vec(),
            timestamp: now_millis(),
        }
    }
}

/// Returns current time as Unix milliseconds.
fn now_millis() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("system clock before UNIX epoch")
        .as_millis() as u64
}

// ---------------------------------------------------------------------------
// Codec
// ---------------------------------------------------------------------------

/// Minimum wire size: 1 (verb) + 4 (msg_id) + 8 (ts) + 2 (sender_len) + 4 (payload_len) = 19.
const MIN_HEADER_SIZE: usize = 19;

/// Encodes and decodes `UacpMessage` values to/from the compact binary wire format.
#[derive(Debug, Clone, Default)]
pub struct UacpCodec;

impl UacpCodec {
    /// Serialize a single message to the binary wire format.
    pub fn encode(msg: &UacpMessage) -> Vec<u8> {
        let sender_bytes = msg.sender_id.as_bytes();
        let sender_len = sender_bytes.len() as u16;
        let payload_len = msg.payload.len() as u32;

        let total = MIN_HEADER_SIZE + sender_bytes.len() + msg.payload.len();
        let mut buf = Vec::with_capacity(total);

        buf.push(msg.verb as u8);
        buf.extend_from_slice(&msg.message_id.to_be_bytes());
        buf.extend_from_slice(&msg.timestamp.to_be_bytes());
        buf.extend_from_slice(&sender_len.to_be_bytes());
        buf.extend_from_slice(sender_bytes);
        buf.extend_from_slice(&payload_len.to_be_bytes());
        buf.extend_from_slice(&msg.payload);

        buf
    }

    /// Deserialize a single message from the binary wire format.
    pub fn decode(data: &[u8]) -> anyhow::Result<UacpMessage> {
        if data.len() < MIN_HEADER_SIZE {
            anyhow::bail!(
                "uACP frame too short: {} bytes (minimum {})",
                data.len(),
                MIN_HEADER_SIZE
            );
        }

        let mut pos = 0;

        // verb
        let verb = UacpVerb::from_byte(data[pos])?;
        pos += 1;

        // message_id
        let message_id = u32::from_be_bytes(data[pos..pos + 4].try_into()?);
        pos += 4;

        // timestamp
        let timestamp = u64::from_be_bytes(data[pos..pos + 8].try_into()?);
        pos += 8;

        // sender
        let sender_len = u16::from_be_bytes(data[pos..pos + 2].try_into()?) as usize;
        pos += 2;

        if pos + sender_len > data.len() {
            anyhow::bail!(
                "uACP sender_len ({sender_len}) exceeds remaining data ({})",
                data.len() - pos
            );
        }
        let sender_id = String::from_utf8(data[pos..pos + sender_len].to_vec())
            .map_err(|_| anyhow::anyhow!("uACP sender_id is not valid UTF-8"))?;
        pos += sender_len;

        // payload
        if pos + 4 > data.len() {
            anyhow::bail!("uACP frame truncated: missing payload_len");
        }
        let payload_len = u32::from_be_bytes(data[pos..pos + 4].try_into()?) as usize;
        pos += 4;

        if pos + payload_len > data.len() {
            anyhow::bail!(
                "uACP payload_len ({payload_len}) exceeds remaining data ({})",
                data.len() - pos
            );
        }
        let payload = data[pos..pos + payload_len].to_vec();

        Ok(UacpMessage {
            verb,
            message_id,
            sender_id,
            payload,
            timestamp,
        })
    }

    /// Encode multiple messages into a single buffer (concatenated frames).
    pub fn encode_batch(msgs: &[UacpMessage]) -> Vec<u8> {
        let mut buf = Vec::new();
        for msg in msgs {
            buf.extend_from_slice(&Self::encode(msg));
        }
        buf
    }

    /// Decode all messages from a concatenated buffer.
    pub fn decode_batch(data: &[u8]) -> anyhow::Result<Vec<UacpMessage>> {
        let mut msgs = Vec::new();
        let mut pos = 0;

        while pos < data.len() {
            // We need to figure out message length by peeking at the header.
            if pos + MIN_HEADER_SIZE > data.len() {
                anyhow::bail!(
                    "uACP batch: trailing {} bytes too short for a header",
                    data.len() - pos
                );
            }

            // Parse sender_len to compute full frame size.
            let sender_len = u16::from_be_bytes(data[pos + 13..pos + 15].try_into()?) as usize;

            // payload_len field sits right after sender bytes:
            // pos + 15 + sender_len  (15 = 1 verb + 4 msg_id + 8 ts + 2 sender_len)
            let pl_off = pos + 15 + sender_len;
            if pl_off + 4 > data.len() {
                anyhow::bail!("uACP batch: frame truncated at payload_len");
            }
            let payload_len = u32::from_be_bytes(data[pl_off..pl_off + 4].try_into()?) as usize;

            let frame_len = MIN_HEADER_SIZE + sender_len + payload_len;
            if pos + frame_len > data.len() {
                anyhow::bail!("uACP batch: frame overflows buffer");
            }

            let msg = Self::decode(&data[pos..pos + frame_len])?;
            msgs.push(msg);
            pos += frame_len;
        }

        Ok(msgs)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // Cross-language interop test vector.
    // verb=PING, message_id=42, sender_id="node-1", timestamp=1700000000000, payload=b""
    // Expected hex: 010000002a0000018bcfe5680000066e6f64652d3100000000
    const INTEROP_HEX: &str = "010000002a0000018bcfe5680000066e6f64652d3100000000";

    fn make_test_message(verb: UacpVerb, payload: &[u8]) -> UacpMessage {
        UacpMessage {
            verb,
            message_id: 1,
            sender_id: "test-agent".to_string(),
            payload: payload.to_vec(),
            timestamp: 1_700_000_000_000,
        }
    }

    #[test]
    fn roundtrip_ping() {
        let msg = make_test_message(UacpVerb::Ping, &[]);
        let encoded = UacpCodec::encode(&msg);
        let decoded = UacpCodec::decode(&encoded).unwrap();
        assert_eq!(decoded.verb, UacpVerb::Ping);
        assert_eq!(decoded.message_id, msg.message_id);
        assert_eq!(decoded.sender_id, msg.sender_id);
        assert_eq!(decoded.payload, msg.payload);
        assert_eq!(decoded.timestamp, msg.timestamp);
    }

    #[test]
    fn roundtrip_tell() {
        let msg = make_test_message(UacpVerb::Tell, b"hello world");
        let encoded = UacpCodec::encode(&msg);
        let decoded = UacpCodec::decode(&encoded).unwrap();
        assert_eq!(decoded.verb, UacpVerb::Tell);
        assert_eq!(decoded.payload, b"hello world");
    }

    #[test]
    fn roundtrip_ask() {
        let msg = make_test_message(UacpVerb::Ask, b"question?");
        let encoded = UacpCodec::encode(&msg);
        let decoded = UacpCodec::decode(&encoded).unwrap();
        assert_eq!(decoded.verb, UacpVerb::Ask);
        assert_eq!(decoded.payload, b"question?");
    }

    #[test]
    fn roundtrip_observe() {
        let msg = make_test_message(UacpVerb::Observe, b"metric=42");
        let encoded = UacpCodec::encode(&msg);
        let decoded = UacpCodec::decode(&encoded).unwrap();
        assert_eq!(decoded.verb, UacpVerb::Observe);
        assert_eq!(decoded.payload, b"metric=42");
    }

    #[test]
    fn roundtrip_empty_payload() {
        let msg = make_test_message(UacpVerb::Tell, &[]);
        let encoded = UacpCodec::encode(&msg);
        let decoded = UacpCodec::decode(&encoded).unwrap();
        assert!(decoded.payload.is_empty());
    }

    #[test]
    fn roundtrip_large_payload() {
        let payload = vec![0xAB_u8; 1_000_000]; // 1 MB
        let msg = make_test_message(UacpVerb::Tell, &payload);
        let encoded = UacpCodec::encode(&msg);
        let decoded = UacpCodec::decode(&encoded).unwrap();
        assert_eq!(decoded.payload.len(), 1_000_000);
        assert_eq!(decoded.payload, payload);
    }

    #[test]
    fn batch_roundtrip() {
        let msgs = vec![
            make_test_message(UacpVerb::Ping, &[]),
            make_test_message(UacpVerb::Tell, b"data"),
            make_test_message(UacpVerb::Ask, b"q"),
        ];
        let encoded = UacpCodec::encode_batch(&msgs);
        let decoded = UacpCodec::decode_batch(&encoded).unwrap();
        assert_eq!(decoded.len(), 3);
        assert_eq!(decoded[0].verb, UacpVerb::Ping);
        assert_eq!(decoded[1].verb, UacpVerb::Tell);
        assert_eq!(decoded[2].verb, UacpVerb::Ask);
        assert_eq!(decoded[1].payload, b"data");
    }

    #[test]
    fn decode_invalid_verb() {
        let mut data = UacpCodec::encode(&make_test_message(UacpVerb::Ping, &[]));
        data[0] = 0xFF; // invalid verb
        let result = UacpCodec::decode(&data);
        assert!(result.is_err());
        let err = result.unwrap_err().to_string();
        assert!(err.contains("invalid uACP verb byte"));
    }

    #[test]
    fn decode_truncated_data() {
        let data = vec![0x01, 0x00]; // way too short
        let result = UacpCodec::decode(&data);
        assert!(result.is_err());
        let err = result.unwrap_err().to_string();
        assert!(err.contains("too short"));
    }

    #[test]
    fn decode_invalid_utf8_sender() {
        let msg = make_test_message(UacpVerb::Ping, &[]);
        let mut data = UacpCodec::encode(&msg);
        // The sender starts at offset 15 (1+4+8+2). Overwrite with invalid UTF-8.
        let sender_start = 15;
        // sender_id is "test-agent" (10 bytes); corrupt first byte.
        data[sender_start] = 0xFF;
        data[sender_start + 1] = 0xFE;
        let result = UacpCodec::decode(&data);
        assert!(result.is_err());
        let err = result.unwrap_err().to_string();
        assert!(err.contains("UTF-8"));
    }

    #[test]
    fn encode_batch_decode_batch_roundtrip() {
        let msgs: Vec<UacpMessage> = (0..5)
            .map(|i| UacpMessage {
                verb: UacpVerb::Tell,
                message_id: i,
                sender_id: format!("agent-{i}"),
                payload: format!("payload-{i}").into_bytes(),
                timestamp: 1_700_000_000_000 + u64::from(i),
            })
            .collect();
        let encoded = UacpCodec::encode_batch(&msgs);
        let decoded = UacpCodec::decode_batch(&encoded).unwrap();
        assert_eq!(decoded.len(), 5);
        for (i, m) in decoded.iter().enumerate() {
            assert_eq!(m.message_id, i as u32);
            assert_eq!(m.sender_id, format!("agent-{i}"));
            assert_eq!(m.payload, format!("payload-{i}").into_bytes());
        }
    }

    #[test]
    fn interop_test_vector() {
        let msg = UacpMessage {
            verb: UacpVerb::Ping,
            message_id: 42,
            sender_id: "node-1".to_string(),
            payload: Vec::new(),
            timestamp: 1_700_000_000_000,
        };
        let encoded = UacpCodec::encode(&msg);
        let hex = encoded
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect::<String>();
        assert_eq!(hex, INTEROP_HEX, "cross-language interop hex mismatch");

        // Also verify we can decode from the known hex.
        let from_hex: Vec<u8> = (0..INTEROP_HEX.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&INTEROP_HEX[i..i + 2], 16).unwrap())
            .collect();
        let decoded = UacpCodec::decode(&from_hex).unwrap();
        assert_eq!(decoded.verb, UacpVerb::Ping);
        assert_eq!(decoded.message_id, 42);
        assert_eq!(decoded.sender_id, "node-1");
        assert!(decoded.payload.is_empty());
        assert_eq!(decoded.timestamp, 1_700_000_000_000);
    }
}

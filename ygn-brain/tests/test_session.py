"""Tests for Session & EventLog."""

from ygn_brain.context_compiler.session import EventLog, Session


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

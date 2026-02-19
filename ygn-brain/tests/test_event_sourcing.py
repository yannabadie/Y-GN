"""Tests for event sourcing — append, replay, snapshot, clear."""

from ygn_brain.event_sourcing import FSMEvent, InMemoryEventStore
from ygn_brain.fsm import Phase


def test_append_and_retrieve_events():
    """Appended events are retrievable."""
    store = InMemoryEventStore()
    evt = FSMEvent(
        from_phase=Phase.IDLE.value,
        to_phase=Phase.DIAGNOSIS.value,
        trigger="user_input",
        session_id="s1",
    )
    store.append(evt)

    all_events = store.events()
    assert len(all_events) == 1
    assert all_events[0].from_phase == Phase.IDLE.value
    assert all_events[0].to_phase == Phase.DIAGNOSIS.value
    assert all_events[0].trigger == "user_input"


def test_events_filtered_by_session():
    """Events can be filtered by session_id."""
    store = InMemoryEventStore()
    store.append(FSMEvent(from_phase="idle", to_phase="diagnosis", session_id="s1"))
    store.append(FSMEvent(from_phase="idle", to_phase="diagnosis", session_id="s2"))
    store.append(FSMEvent(from_phase="diagnosis", to_phase="analysis", session_id="s1"))

    s1_events = store.events(session_id="s1")
    assert len(s1_events) == 2
    s2_events = store.events(session_id="s2")
    assert len(s2_events) == 1


def test_replay_all_events():
    """Replay without target returns the final phase."""
    store = InMemoryEventStore()
    store.append(FSMEvent(from_phase="idle", to_phase="diagnosis"))
    store.append(FSMEvent(from_phase="diagnosis", to_phase="analysis"))
    store.append(FSMEvent(from_phase="analysis", to_phase="planning"))

    phase = store.replay()
    assert phase == Phase.PLANNING


def test_replay_to_specific_event():
    """Replay up to a specific event_id stops at that event."""
    store = InMemoryEventStore()
    evt1 = FSMEvent(from_phase="idle", to_phase="diagnosis")
    evt2 = FSMEvent(from_phase="diagnosis", to_phase="analysis")
    evt3 = FSMEvent(from_phase="analysis", to_phase="planning")
    store.append(evt1)
    store.append(evt2)
    store.append(evt3)

    phase = store.replay(target_event_id=evt2.event_id)
    assert phase == Phase.ANALYSIS


def test_snapshot():
    """Snapshot returns correct state dict for a session."""
    store = InMemoryEventStore()
    evt = FSMEvent(from_phase="idle", to_phase="diagnosis", session_id="session-abc")
    store.append(evt)

    snap = store.snapshot("session-abc")
    assert snap["session_id"] == "session-abc"
    assert snap["current_phase"] == "diagnosis"
    assert snap["event_count"] == 1
    assert snap["last_event_timestamp"] is not None


def test_snapshot_empty_session():
    """Snapshot for a session with no events returns idle state."""
    store = InMemoryEventStore()
    snap = store.snapshot("nonexistent")
    assert snap["current_phase"] == Phase.IDLE.value
    assert snap["event_count"] == 0
    assert snap["last_event_timestamp"] is None


def test_clear_all():
    """Clear without session removes all events."""
    store = InMemoryEventStore()
    store.append(FSMEvent(from_phase="idle", to_phase="diagnosis", session_id="s1"))
    store.append(FSMEvent(from_phase="idle", to_phase="diagnosis", session_id="s2"))

    count = store.clear()
    assert count == 2
    assert store.events() == []


def test_clear_by_session():
    """Clear with session_id removes only that session's events."""
    store = InMemoryEventStore()
    store.append(FSMEvent(from_phase="idle", to_phase="diagnosis", session_id="s1"))
    store.append(FSMEvent(from_phase="idle", to_phase="diagnosis", session_id="s2"))

    count = store.clear(session_id="s1")
    assert count == 1
    remaining = store.events()
    assert len(remaining) == 1
    assert remaining[0].session_id == "s2"


def test_empty_store_replay():
    """Replaying an empty store returns IDLE."""
    store = InMemoryEventStore()
    phase = store.replay()
    assert phase == Phase.IDLE

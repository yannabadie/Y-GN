"""Tests for FSM module."""

import pytest

from ygn_brain.fsm import FSMState, Phase


def test_initial_state_is_idle():
    state = FSMState()
    assert state.phase == Phase.IDLE


def test_valid_transition_chain():
    state = FSMState()
    for target in [
        Phase.DIAGNOSIS,
        Phase.ANALYSIS,
        Phase.PLANNING,
        Phase.EXECUTION,
        Phase.VALIDATION,
        Phase.SYNTHESIS,
        Phase.COMPLETE,
    ]:
        state = state.transition(target)
    assert state.phase == Phase.COMPLETE


def test_invalid_transition_raises():
    state = FSMState()
    with pytest.raises(ValueError, match="Invalid transition"):
        state.transition(Phase.EXECUTION)


def test_validation_can_retry_execution():
    state = FSMState(phase=Phase.VALIDATION)
    retried = state.transition(Phase.EXECUTION)
    assert retried.phase == Phase.EXECUTION

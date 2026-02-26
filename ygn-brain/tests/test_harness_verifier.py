"""Tests for harness verifiers."""

import pytest

from ygn_brain.harness.types import Candidate
from ygn_brain.harness.verifier import CommandVerifier, TextVerifier, Verifier


def _make_candidate(output: str) -> Candidate:
    return Candidate(
        id="c1",
        provider="stub",
        model="stub",
        prompt="test",
        output=output,
        latency_ms=0,
        token_count=0,
    )


def test_verifier_is_abstract():
    with pytest.raises(TypeError):
        Verifier()  # type: ignore[abstract]


def test_text_verifier_passes_good_output():
    v = TextVerifier()
    fb = v.verify(_make_candidate("Here is a detailed analysis of the problem."), "analyze this")
    assert fb.passed is True
    assert fb.score > 0.5


def test_text_verifier_fails_refusal():
    v = TextVerifier()
    fb = v.verify(_make_candidate("I cannot help with that."), "analyze this")
    assert fb.score < 0.5


def test_text_verifier_fails_empty():
    v = TextVerifier()
    fb = v.verify(_make_candidate(""), "analyze this")
    assert fb.passed is False
    assert fb.score == 0.0


def test_command_verifier_success():
    v = CommandVerifier(command='python -c "print(42)"')
    fb = v.verify(_make_candidate("some output"), "task")
    assert fb.passed is True
    assert fb.score == 1.0


def test_command_verifier_failure():
    v = CommandVerifier(command='python -c "import sys; sys.exit(1)"')
    fb = v.verify(_make_candidate("some output"), "task")
    assert fb.passed is False
    assert fb.score == 0.0

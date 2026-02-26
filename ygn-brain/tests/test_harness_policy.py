"""Tests for policy and selector."""

from ygn_brain.harness.policy import DefaultPolicy
from ygn_brain.harness.selector import ConsensusSelector
from ygn_brain.harness.types import Candidate, Feedback


def _c(cid: str, provider: str, output: str) -> Candidate:
    return Candidate(id=cid, provider=provider, model="m", prompt="p",
                     output=output, latency_ms=100, token_count=10)


def _f(score: float, passed: bool = True) -> Feedback:
    return Feedback(passed=passed, score=score, diagnostics="ok")


def test_default_policy_continues():
    p = DefaultPolicy(max_rounds=3, min_score=0.8)
    assert p.should_continue(1, 0.5, []) is True


def test_default_policy_stops_at_max_rounds():
    p = DefaultPolicy(max_rounds=3, min_score=0.8)
    assert p.should_continue(3, 0.5, []) is False


def test_default_policy_stops_at_min_score():
    p = DefaultPolicy(max_rounds=3, min_score=0.8)
    assert p.should_continue(1, 0.9, []) is False


def test_default_policy_refines_prompt():
    p = DefaultPolicy(max_rounds=3, min_score=0.8)
    fb = Feedback(passed=False, score=0.3, diagnostics="Missing detail X")
    refined = p.refine_prompt("original task", fb)
    assert "Missing detail X" in refined
    assert "original task" in refined


def test_consensus_selector_picks_highest_score():
    sel = ConsensusSelector()
    c1 = _c("a", "codex", "answer A")
    c2 = _c("b", "gemini", "answer B")
    winner = sel.select([(c1, _f(0.7)), (c2, _f(0.9))])
    assert winner.id == "b"


def test_consensus_selector_bonus_for_agreement():
    sel = ConsensusSelector()
    c1 = _c("a", "codex", "the answer is 42")
    c2 = _c("b", "gemini", "the answer is 42")
    c3 = _c("c", "codex", "something different entirely")
    winner = sel.select([(c1, _f(0.7)), (c2, _f(0.7)), (c3, _f(0.75))])
    assert winner.id in ("a", "b")

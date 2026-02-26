"""Tests for harness type definitions."""

from ygn_brain.harness.types import (
    POETIQ_PRESET,
    Candidate,
    Feedback,
    HarnessConfig,
    HarnessResult,
)


def test_candidate_dataclass():
    c = Candidate(
        id="c1", provider="codex", model="gpt-5.2-codex",
        prompt="solve X", output="answer Y",
        latency_ms=150.0, token_count=42,
    )
    assert c.provider == "codex"
    assert c.latency_ms == 150.0


def test_feedback_dataclass():
    f = Feedback(passed=True, score=0.85, diagnostics="all good", artifacts={})
    assert f.passed is True
    assert f.score == 0.85


def test_harness_config_defaults():
    cfg = HarnessConfig()
    assert cfg.max_rounds == 3
    assert cfg.min_score == 0.8
    assert cfg.ensemble is True
    assert "codex" in cfg.providers
    assert "gemini" in cfg.providers


def test_poetiq_preset():
    assert POETIQ_PRESET.max_rounds == 3
    assert POETIQ_PRESET.ensemble is True
    assert len(POETIQ_PRESET.providers) == 2


def test_harness_result():
    c = Candidate(id="c1", provider="codex", model="m", prompt="p",
                  output="o", latency_ms=0, token_count=0)
    f = Feedback(passed=True, score=0.9, diagnostics="ok", artifacts={})
    r = HarnessResult(winner=c, feedback=f, rounds_used=2, total_candidates=4)
    assert r.rounds_used == 2

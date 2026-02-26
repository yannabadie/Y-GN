"""Benchmark: RegexGuard vs RegexGuard+ML on attack templates.

These tests compare detection rates of the guard pipeline against the
10 Red/Blue attack templates from swarm.py.  Run with:

    pytest tests/test_guard_benchmark.py -v -s
"""

from __future__ import annotations

from ygn_brain.guard import GuardPipeline, RegexGuard
from ygn_brain.guard_ml import OnnxClassifierGuard
from ygn_brain.swarm import _ATTACK_TEMPLATES


def test_attack_templates_exist():
    """Sanity: _ATTACK_TEMPLATES is non-empty and well-formed."""
    assert len(_ATTACK_TEMPLATES) == 10
    for entry in _ATTACK_TEMPLATES:
        assert "name" in entry
        assert "text" in entry
        assert len(entry["text"]) > 0


def test_regex_only_coverage():
    """Measure how many attack templates regex catches."""
    pipeline = GuardPipeline(guards=[RegexGuard()])
    blocked = 0
    for template in _ATTACK_TEMPLATES:
        result = pipeline.evaluate(template["text"])
        if not result.allowed:
            blocked += 1
    # Regex should catch at least some attacks
    assert blocked >= 3
    # Document coverage
    coverage = blocked / len(_ATTACK_TEMPLATES) * 100
    print(f"\nRegex coverage: {blocked}/{len(_ATTACK_TEMPLATES)} = {coverage:.0f}%")


def test_regex_plus_ml_stub_coverage():
    """With ML stub (always passes), coverage should equal regex-only."""
    regex_pipe = GuardPipeline(guards=[RegexGuard()])
    ml_pipe = GuardPipeline(guards=[RegexGuard(), OnnxClassifierGuard(stub=True)])

    for template in _ATTACK_TEMPLATES:
        regex_result = regex_pipe.evaluate(template["text"])
        ml_result = ml_pipe.evaluate(template["text"])
        # ML stub doesn't add detection, so results should match
        assert regex_result.allowed == ml_result.allowed


def test_blocked_attacks_have_nonzero_score():
    """Every blocked attack must report a positive threat score."""
    pipeline = GuardPipeline(guards=[RegexGuard()])
    for template in _ATTACK_TEMPLATES:
        result = pipeline.evaluate(template["text"])
        if not result.allowed:
            assert result.score > 0.0, f"Blocked attack '{template['name']}' has zero score"


def test_passed_attacks_are_known_gaps():
    """Attacks that pass regex are known evasion classes (unicode, base64, etc.)."""
    known_gaps = {
        "unicode_homoglyph",
        "base64_encoded",
        "multilingual",
        "tool_abuse",
        "data_exfiltration",
    }
    pipeline = GuardPipeline(guards=[RegexGuard()])
    for template in _ATTACK_TEMPLATES:
        result = pipeline.evaluate(template["text"])
        if result.allowed:
            assert template["name"] in known_gaps, (
                f"Unexpected pass: '{template['name']}' — update known_gaps or fix regex"
            )

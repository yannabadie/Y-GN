"""Tests for token budget tracker."""

import pytest

from ygn_brain.context_compiler.token_budget import TokenBudget


def test_budget_tracking():
    budget = TokenBudget(max_tokens=100)
    assert budget.remaining() == 100
    assert budget.is_within_budget()

    budget.consume(60)
    assert budget.remaining() == 40
    assert budget.is_within_budget()

    budget.consume(50)
    assert budget.remaining() == -10
    assert not budget.is_within_budget()
    assert budget.overflow() == 10


def test_budget_requires_explicit_max():
    with pytest.raises(ValueError, match="max_tokens must be positive"):
        TokenBudget(max_tokens=0)

    with pytest.raises(ValueError, match="max_tokens must be positive"):
        TokenBudget(max_tokens=-1)


def test_estimate_tokens():
    from ygn_brain.context_compiler.token_budget import estimate_tokens

    assert estimate_tokens("hello world") == 3  # 2 words * 1.3 ~ 2.6 -> 3
    assert estimate_tokens("") == 0
    assert estimate_tokens("a " * 100) > 100  # 100 words * 1.3 = 130

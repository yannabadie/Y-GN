"""Tests for cosine similarity."""

from ygn_brain.cosine import cosine_similarity


def test_identical_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_opposite_vectors():
    assert abs(cosine_similarity([1.0, 0.0], [-1.0, 0.0]) - (-1.0)) < 1e-6


def test_similar_vectors():
    score = cosine_similarity([1.0, 1.0], [1.0, 0.9])
    assert 0.99 < score < 1.0


def test_zero_vector_returns_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_empty_vectors_returns_zero():
    assert cosine_similarity([], []) == 0.0

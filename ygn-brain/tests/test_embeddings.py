"""Tests for the embedding service abstraction."""

import pytest
from ygn_brain.embeddings import EmbeddingService, StubEmbeddingService


def test_stub_embedding_dimension():
    svc = StubEmbeddingService(dimension=384)
    assert svc.dimension() == 384


def test_stub_embedding_returns_zero_vectors():
    svc = StubEmbeddingService(dimension=4)
    results = svc.embed(["hello", "world"])
    assert len(results) == 2
    assert len(results[0]) == 4
    assert all(v == 0.0 for v in results[0])


def test_stub_embedding_empty_input():
    svc = StubEmbeddingService(dimension=384)
    results = svc.embed([])
    assert results == []


def test_embedding_service_is_abstract():
    with pytest.raises(TypeError):
        EmbeddingService()  # type: ignore[abstract]

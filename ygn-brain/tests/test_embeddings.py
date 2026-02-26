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


from unittest.mock import patch, MagicMock


def test_ollama_embedding_calls_api():
    from ygn_brain.embeddings import OllamaEmbeddingService

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}

    with patch("ygn_brain.embeddings.requests.post", return_value=mock_response) as mock_post:
        svc = OllamaEmbeddingService(model="nomic-embed-text", dimension=3)
        result = svc.embed(["hello"])
        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]
        mock_post.assert_called_once()


def test_ollama_embedding_batch():
    from ygn_brain.embeddings import OllamaEmbeddingService

    call_count = 0

    def fake_post(url, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"embedding": [float(call_count)] * 3}
        return resp

    with patch("ygn_brain.embeddings.requests.post", side_effect=fake_post):
        svc = OllamaEmbeddingService(model="nomic-embed-text", dimension=3)
        result = svc.embed(["a", "b", "c"])
        assert len(result) == 3
        assert call_count == 3  # one API call per text


def test_ollama_embedding_dimension():
    from ygn_brain.embeddings import OllamaEmbeddingService

    svc = OllamaEmbeddingService(model="nomic-embed-text", dimension=768)
    assert svc.dimension() == 768

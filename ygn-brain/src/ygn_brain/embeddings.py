"""Embedding service abstraction for semantic search.

Provides ABC and concrete backends:
- StubEmbeddingService: zero vectors (for testing)
- LocalEmbeddingService: sentence-transformers (optional dep)
- OllamaEmbeddingService: Ollama /api/embeddings (optional dep)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import requests


class EmbeddingService(ABC):
    """Abstract base class for embedding backends."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors."""

    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""


class StubEmbeddingService(EmbeddingService):
    """Returns zero vectors. For testing without ML dependencies."""

    def __init__(self, dimension: int = 384) -> None:
        self._dim = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._dim for _ in texts]

    def dimension(self) -> int:
        return self._dim


class OllamaEmbeddingService(EmbeddingService):
    """Embedding via Ollama /api/embeddings endpoint.

    Requires Ollama running locally (default: http://localhost:11434).
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        dimension: int = 768,
        base_url: str = "http://localhost:11434",
        timeout: float = 30.0,
    ) -> None:
        self._model = model
        self._dim = dimension
        self._url = f"{base_url}/api/embeddings"
        self._timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            resp = requests.post(
                self._url,
                json={"model": self._model, "prompt": text},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            results.append(resp.json()["embedding"])
        return results

    def dimension(self) -> int:
        return self._dim


# Dimensions for known models
_MODEL_DIMENSIONS: dict[str, int] = {
    "all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
    "nomic-embed-text": 768,
}


class LocalEmbeddingService(EmbeddingService):
    """Embedding via sentence-transformers (local CPU inference).

    Requires: pip install 'ygn-brain[ml]'
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._dim = _MODEL_DIMENSIONS.get(model_name, 384)
        self._model = None  # lazy load

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers required. Install with: "
                    "pip install 'ygn-brain[ml]'"
                ) from e
            self._model = SentenceTransformer(self._model_name)
            self._dim = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._load_model()
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [row.tolist() for row in embeddings]

    def dimension(self) -> int:
        return self._dim

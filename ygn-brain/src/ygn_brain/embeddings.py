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

"""Embedding service abstraction for semantic search.

Provides ABC and concrete backends:
- StubEmbeddingService: zero vectors (for testing)
- LocalEmbeddingService: sentence-transformers (optional dep)
- OllamaEmbeddingService: Ollama /api/embeddings (optional dep)
"""

from __future__ import annotations

from abc import ABC, abstractmethod


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

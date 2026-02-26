"""Entity extraction for Temporal Knowledge Graph."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod


class EntityExtractor(ABC):
    """Abstract base for entity extraction backends."""

    @abstractmethod
    def extract(self, text: str) -> list[str]:
        """Extract entities from text."""


class StubEntityExtractor(EntityExtractor):
    """Returns empty list. For testing."""

    def extract(self, text: str) -> list[str]:
        return []


class RegexEntityExtractor(EntityExtractor):
    """Pattern-based entity extraction.

    Extracts: function names, class names, URLs, file paths.
    """

    _PATTERNS = [
        (r"\bdef\s+(\w+)", "func"),
        (r"\bclass\s+(\w+)", "class"),
        (r"\bfn\s+(\w+)", "func"),
        (r"(https?://\S+)", "url"),
        (r"(/[\w/.-]+\.\w+)", "path"),
    ]

    def extract(self, text: str) -> list[str]:
        if not text:
            return []
        entities: list[str] = []
        for pattern, _ in self._PATTERNS:
            for match in re.finditer(pattern, text):
                entity = match.group(1) if match.lastindex else match.group(0)
                if entity not in entities:
                    entities.append(entity)
        return entities

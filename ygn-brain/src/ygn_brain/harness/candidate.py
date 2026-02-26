"""Candidate generation for the Refinement Harness."""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod

from ygn_brain.harness.types import Candidate, HarnessConfig

_log = logging.getLogger(__name__)


class CandidateGenerator(ABC):
    """Abstract base for candidate generation."""

    @abstractmethod
    async def generate(
        self,
        task: str,
        context: str,
        config: HarnessConfig,
    ) -> list[Candidate]:
        """Generate candidates from configured providers."""


class StubCandidateGenerator(CandidateGenerator):
    """Returns fixed output. For testing."""

    def __init__(self, output: str = "stub output") -> None:
        self._output = output

    async def generate(
        self,
        task: str,
        context: str,
        config: HarnessConfig,
    ) -> list[Candidate]:
        candidates: list[Candidate] = []
        for provider in config.providers:
            for _ in range(config.candidates_per_provider):
                candidates.append(
                    Candidate(
                        id=uuid.uuid4().hex[:8],
                        provider=provider,
                        model="stub",
                        prompt=task,
                        output=self._output,
                        latency_ms=0.0,
                        token_count=len(self._output.split()),
                    )
                )
        return candidates


class MultiProviderGenerator(CandidateGenerator):
    """Generates candidates via real LLM providers (Codex + Gemini CLI).

    Uses ``ProviderFactory`` to instantiate providers by name.
    """

    async def generate(
        self,
        task: str,
        context: str,
        config: HarnessConfig,
    ) -> list[Candidate]:
        from ygn_brain.provider import ChatMessage, ChatRequest, ChatRole
        from ygn_brain.provider_factory import ProviderFactory

        candidates: list[Candidate] = []
        for provider_name in config.providers:
            try:
                provider = ProviderFactory._create_explicit(provider_name)
            except (ValueError, Exception):
                _log.warning("Skipping unavailable provider: %s", provider_name)
                continue

            model_name = getattr(provider, "model", provider_name)

            for _ in range(config.candidates_per_provider):
                prompt = f"{context}\n\n{task}" if context else task
                request = ChatRequest(
                    model=model_name,
                    messages=[
                        ChatMessage(role=ChatRole.USER, content=prompt),
                    ],
                )
                start = time.monotonic()
                try:
                    response = await provider.chat(request)
                    latency = (time.monotonic() - start) * 1000
                    total_tokens = 0
                    if response.usage is not None:
                        total_tokens = (
                            response.usage.prompt_tokens
                            + response.usage.completion_tokens
                        )
                    candidates.append(
                        Candidate(
                            id=uuid.uuid4().hex[:8],
                            provider=provider_name,
                            model=model_name,
                            prompt=prompt,
                            output=response.content,
                            latency_ms=latency,
                            token_count=total_tokens,
                        )
                    )
                except Exception:  # noqa: BLE001
                    _log.warning("Provider %s chat failed", provider_name, exc_info=True)
                    continue
        return candidates

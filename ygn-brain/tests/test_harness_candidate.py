"""Tests for candidate generation."""

import pytest

from ygn_brain.harness.candidate import CandidateGenerator, StubCandidateGenerator
from ygn_brain.harness.types import HarnessConfig


def test_generator_is_abstract():
    with pytest.raises(TypeError):
        CandidateGenerator()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_stub_generator_produces_candidates():
    gen = StubCandidateGenerator(output="stub answer")
    config = HarnessConfig(providers=["stub"], candidates_per_provider=2)
    candidates = await gen.generate("test task", "", config)
    assert len(candidates) == 2
    assert all(c.output == "stub answer" for c in candidates)
    assert all(c.provider == "stub" for c in candidates)


@pytest.mark.asyncio
async def test_stub_generator_unique_ids():
    gen = StubCandidateGenerator(output="answer")
    config = HarnessConfig(providers=["stub"], candidates_per_provider=3)
    candidates = await gen.generate("task", "", config)
    ids = [c.id for c in candidates]
    assert len(set(ids)) == 3

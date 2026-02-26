# Refinement Harness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Poetiq-inspired generate-verify-refine engine with multi-provider ensemble, full EvidencePack tracing, and zero API cost (Codex + Gemini CLI only).

**Architecture:** 5 abstract components (CandidateGenerator, Verifier, RefinementPolicy, Selector, MemoryStore) composed in a RefinementHarness engine. Each iteration traces to EvidencePack. Poetiq is a preset configuration. Includes drift fixes (README, MCP version).

**Tech Stack:** Python 3.11+, existing LLMProvider/ProviderFactory, EvidencePack, TieredMemoryService, cosine_similarity. Codex CLI + Gemini CLI for E2E tests.

**Design doc:** `docs/plans/2026-02-26-refinement-harness-design.md`

---

## Task 1: Types dataclasses

**Files:**
- Create: `ygn-brain/src/ygn_brain/harness/__init__.py`
- Create: `ygn-brain/src/ygn_brain/harness/types.py`
- Create: `ygn-brain/tests/test_harness_types.py`

**Step 1: Write the failing tests**

```python
# ygn-brain/tests/test_harness_types.py
"""Tests for harness type definitions."""

from ygn_brain.harness.types import (
    Candidate,
    Feedback,
    HarnessConfig,
    HarnessResult,
    POETIQ_PRESET,
)


def test_candidate_dataclass():
    c = Candidate(
        id="c1",
        provider="codex",
        model="gpt-5.2-codex",
        prompt="solve X",
        output="answer Y",
        latency_ms=150.0,
        token_count=42,
    )
    assert c.provider == "codex"
    assert c.latency_ms == 150.0


def test_feedback_dataclass():
    f = Feedback(passed=True, score=0.85, diagnostics="all good", artifacts={})
    assert f.passed is True
    assert f.score == 0.85


def test_harness_config_defaults():
    cfg = HarnessConfig()
    assert cfg.max_rounds == 3
    assert cfg.min_score == 0.8
    assert cfg.ensemble is True
    assert "codex" in cfg.providers
    assert "gemini" in cfg.providers


def test_poetiq_preset():
    assert POETIQ_PRESET.max_rounds == 3
    assert POETIQ_PRESET.ensemble is True
    assert len(POETIQ_PRESET.providers) == 2


def test_harness_result():
    c = Candidate(id="c1", provider="codex", model="m", prompt="p", output="o", latency_ms=0, token_count=0)
    f = Feedback(passed=True, score=0.9, diagnostics="ok", artifacts={})
    r = HarnessResult(winner=c, feedback=f, rounds_used=2, total_candidates=4)
    assert r.rounds_used == 2
```

**Step 2: Run to verify fail**

Run: `cd ygn-brain && python -m pytest tests/test_harness_types.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Create the harness package and types**

```python
# ygn-brain/src/ygn_brain/harness/__init__.py
"""Refinement Harness — Poetiq-inspired generate-verify-refine engine."""
```

```python
# ygn-brain/src/ygn_brain/harness/types.py
"""Core types for the Refinement Harness."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Candidate:
    """A single candidate output from a provider."""

    id: str
    provider: str
    model: str
    prompt: str
    output: str
    latency_ms: float
    token_count: int


@dataclass
class Feedback:
    """Verification result for a candidate."""

    passed: bool
    score: float  # 0.0 - 1.0
    diagnostics: str
    artifacts: dict = field(default_factory=dict)


@dataclass
class HarnessConfig:
    """Configuration for a refinement harness run."""

    max_rounds: int = 3
    min_score: float = 0.8
    ensemble: bool = True
    providers: list[str] = field(default_factory=lambda: ["codex", "gemini"])
    candidates_per_provider: int = 2
    verifier: str = "text"  # "text" or "command"
    command: str | None = None  # for CommandVerifier


@dataclass
class HarnessResult:
    """Result of a complete harness run."""

    winner: Candidate
    feedback: Feedback
    rounds_used: int
    total_candidates: int


POETIQ_PRESET = HarnessConfig(
    max_rounds=3,
    min_score=0.8,
    ensemble=True,
    providers=["gemini", "codex"],
    candidates_per_provider=2,
    verifier="text",
)
```

**Step 4: Run tests**

Run: `cd ygn-brain && python -m pytest tests/test_harness_types.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add ygn-brain/src/ygn_brain/harness/ ygn-brain/tests/test_harness_types.py
git commit -m "feat(harness): add types — Candidate, Feedback, HarnessConfig, POETIQ_PRESET"
```

---

## Task 2: Verifier ABC + TextVerifier + CommandVerifier

**Files:**
- Create: `ygn-brain/src/ygn_brain/harness/verifier.py`
- Create: `ygn-brain/tests/test_harness_verifier.py`

**Step 1: Write the failing tests**

```python
# ygn-brain/tests/test_harness_verifier.py
"""Tests for harness verifiers."""

import pytest
from ygn_brain.harness.types import Candidate, Feedback
from ygn_brain.harness.verifier import Verifier, TextVerifier, CommandVerifier


def _make_candidate(output: str) -> Candidate:
    return Candidate(
        id="c1", provider="stub", model="stub",
        prompt="test", output=output, latency_ms=0, token_count=0,
    )


def test_verifier_is_abstract():
    with pytest.raises(TypeError):
        Verifier()  # type: ignore[abstract]


def test_text_verifier_passes_good_output():
    v = TextVerifier()
    fb = v.verify(_make_candidate("Here is a detailed analysis of the problem."), "analyze this")
    assert fb.passed is True
    assert fb.score > 0.5


def test_text_verifier_fails_refusal():
    v = TextVerifier()
    fb = v.verify(_make_candidate("I cannot help with that."), "analyze this")
    assert fb.score < 0.5


def test_text_verifier_fails_empty():
    v = TextVerifier()
    fb = v.verify(_make_candidate(""), "analyze this")
    assert fb.passed is False
    assert fb.score == 0.0


def test_command_verifier_success():
    v = CommandVerifier(command="python -c \"print('ok')\"")
    fb = v.verify(_make_candidate("some output"), "task")
    assert fb.passed is True
    assert fb.score == 1.0


def test_command_verifier_failure():
    v = CommandVerifier(command="python -c \"import sys; sys.exit(1)\"")
    fb = v.verify(_make_candidate("some output"), "task")
    assert fb.passed is False
    assert fb.score == 0.0
```

**Step 2: Run to verify fail**: `cd ygn-brain && python -m pytest tests/test_harness_verifier.py -v`

**Step 3: Implement**

```python
# ygn-brain/src/ygn_brain/harness/verifier.py
"""Verification backends for the Refinement Harness."""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod

from ygn_brain.harness.types import Candidate, Feedback

_REFUSAL_PATTERNS = [
    "i cannot", "i can't", "i'm unable", "i am unable",
    "i apologize", "as an ai", "i don't have access",
]


class Verifier(ABC):
    """Abstract base for candidate verification."""

    @abstractmethod
    def verify(self, candidate: Candidate, task: str) -> Feedback:
        """Verify a candidate output against the task."""


class TextVerifier(Verifier):
    """Heuristic text quality verifier.

    Checks: non-empty, no refusal, minimum length, coherence.
    """

    def __init__(self, min_length: int = 20) -> None:
        self._min_length = min_length

    def verify(self, candidate: Candidate, task: str) -> Feedback:
        text = candidate.output.strip()

        if not text:
            return Feedback(passed=False, score=0.0, diagnostics="Empty output")

        score = 0.0
        diagnostics: list[str] = []

        # Length score (0-0.3)
        length_score = min(len(text) / 200.0, 0.3)
        score += length_score

        # Refusal check (0 or 0.3)
        lower = text.lower()
        is_refusal = any(p in lower for p in _REFUSAL_PATTERNS)
        if is_refusal:
            diagnostics.append("Detected refusal pattern")
        else:
            score += 0.3

        # Relevance: task keywords in output (0-0.2)
        task_words = set(task.lower().split())
        output_words = set(lower.split())
        overlap = len(task_words & output_words) / max(len(task_words), 1)
        relevance = min(overlap, 0.2)
        score += relevance

        # Format: has structure (0-0.2)
        has_structure = any(c in text for c in ["\n", "- ", "1.", "```", "##"])
        if has_structure:
            score += 0.2

        passed = score >= 0.5 and not is_refusal
        return Feedback(
            passed=passed,
            score=round(score, 3),
            diagnostics="; ".join(diagnostics) if diagnostics else "ok",
        )


class CommandVerifier(Verifier):
    """Verifier that runs a shell command.

    Score: 1.0 if exit code 0, 0.0 otherwise.
    Captures stdout/stderr in artifacts.
    """

    def __init__(self, command: str, timeout: float = 60.0) -> None:
        self._command = command
        self._timeout = timeout

    def verify(self, candidate: Candidate, task: str) -> Feedback:
        try:
            result = subprocess.run(
                self._command,
                shell=True,  # noqa: S602
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            passed = result.returncode == 0
            return Feedback(
                passed=passed,
                score=1.0 if passed else 0.0,
                diagnostics=f"exit code {result.returncode}",
                artifacts={
                    "stdout": result.stdout[:2000],
                    "stderr": result.stderr[:2000],
                },
            )
        except subprocess.TimeoutExpired:
            return Feedback(
                passed=False,
                score=0.0,
                diagnostics=f"Command timed out after {self._timeout}s",
            )
```

**Step 4: Run tests + ruff**

Run: `cd ygn-brain && python -m pytest tests/test_harness_verifier.py -v && ruff check src/ygn_brain/harness/verifier.py`

**Step 5: Commit**

```bash
git add ygn-brain/src/ygn_brain/harness/verifier.py ygn-brain/tests/test_harness_verifier.py
git commit -m "feat(harness): add Verifier ABC + TextVerifier + CommandVerifier"
```

---

## Task 3: CandidateGenerator ABC + MultiProviderGenerator

**Files:**
- Create: `ygn-brain/src/ygn_brain/harness/candidate.py`
- Create: `ygn-brain/tests/test_harness_candidate.py`

**Step 1: Write the failing tests**

```python
# ygn-brain/tests/test_harness_candidate.py
"""Tests for candidate generation."""

import pytest
from ygn_brain.harness.types import Candidate, HarnessConfig
from ygn_brain.harness.candidate import (
    CandidateGenerator,
    StubCandidateGenerator,
)


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
    assert len(set(ids)) == 3  # all unique
```

**Step 2: Run to verify fail**

**Step 3: Implement**

```python
# ygn-brain/src/ygn_brain/harness/candidate.py
"""Candidate generation for the Refinement Harness."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod

from ygn_brain.harness.types import Candidate, HarnessConfig


class CandidateGenerator(ABC):
    """Abstract base for candidate generation."""

    @abstractmethod
    async def generate(
        self, task: str, context: str, config: HarnessConfig,
    ) -> list[Candidate]:
        """Generate candidates from configured providers."""


class StubCandidateGenerator(CandidateGenerator):
    """Returns fixed output. For testing."""

    def __init__(self, output: str = "stub output") -> None:
        self._output = output

    async def generate(
        self, task: str, context: str, config: HarnessConfig,
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

    Uses ProviderFactory to instantiate providers.
    """

    async def generate(
        self, task: str, context: str, config: HarnessConfig,
    ) -> list[Candidate]:
        from ygn_brain.provider_factory import ProviderFactory
        from ygn_brain.provider import ChatRequest

        candidates: list[Candidate] = []
        for provider_name in config.providers:
            try:
                provider = ProviderFactory.create_by_name(provider_name)
            except Exception:
                continue

            for i in range(config.candidates_per_provider):
                prompt = f"{context}\n\n{task}" if context else task
                request = ChatRequest(
                    messages=[{"role": "user", "content": prompt}],
                    model=provider.model if hasattr(provider, "model") else None,
                )
                start = time.monotonic()
                try:
                    response = await provider.chat(request)
                    latency = (time.monotonic() - start) * 1000
                    candidates.append(
                        Candidate(
                            id=uuid.uuid4().hex[:8],
                            provider=provider_name,
                            model=getattr(provider, "_model", provider_name),
                            prompt=prompt,
                            output=response.content,
                            latency_ms=latency,
                            token_count=response.usage.get("total_tokens", 0)
                            if response.usage
                            else 0,
                        )
                    )
                except Exception:
                    continue
        return candidates
```

Note: `ProviderFactory.create_by_name()` may not exist. Read `provider_factory.py` (lines 52-65) to check. If it uses env var, the MultiProviderGenerator should set env temporarily or use the factory differently. The implementer must adapt to the real API.

**Step 4: Run tests + commit**

```bash
git add ygn-brain/src/ygn_brain/harness/candidate.py ygn-brain/tests/test_harness_candidate.py
git commit -m "feat(harness): add CandidateGenerator ABC + StubCandidateGenerator + MultiProviderGenerator"
```

---

## Task 4: RefinementPolicy + Selector

**Files:**
- Create: `ygn-brain/src/ygn_brain/harness/policy.py`
- Create: `ygn-brain/src/ygn_brain/harness/selector.py`
- Create: `ygn-brain/tests/test_harness_policy.py`

**Step 1: Write the failing tests**

```python
# ygn-brain/tests/test_harness_policy.py
"""Tests for policy and selector."""

from ygn_brain.harness.types import Candidate, Feedback
from ygn_brain.harness.policy import DefaultPolicy
from ygn_brain.harness.selector import ConsensusSelector


def _c(id: str, provider: str, output: str) -> Candidate:
    return Candidate(id=id, provider=provider, model="m", prompt="p",
                     output=output, latency_ms=100, token_count=10)


def _f(score: float, passed: bool = True) -> Feedback:
    return Feedback(passed=passed, score=score, diagnostics="ok")


def test_default_policy_continues():
    p = DefaultPolicy(max_rounds=3, min_score=0.8)
    assert p.should_continue(1, 0.5, []) is True


def test_default_policy_stops_at_max_rounds():
    p = DefaultPolicy(max_rounds=3, min_score=0.8)
    assert p.should_continue(3, 0.5, []) is False


def test_default_policy_stops_at_min_score():
    p = DefaultPolicy(max_rounds=3, min_score=0.8)
    assert p.should_continue(1, 0.9, []) is False


def test_default_policy_refines_prompt():
    p = DefaultPolicy(max_rounds=3, min_score=0.8)
    fb = Feedback(passed=False, score=0.3, diagnostics="Missing detail X")
    refined = p.refine_prompt("original task", fb)
    assert "Missing detail X" in refined
    assert "original task" in refined


def test_consensus_selector_picks_highest_score():
    sel = ConsensusSelector()
    c1 = _c("a", "codex", "answer A")
    c2 = _c("b", "gemini", "answer B")
    winner = sel.select([(c1, _f(0.7)), (c2, _f(0.9))])
    assert winner.id == "b"


def test_consensus_selector_bonus_for_agreement():
    sel = ConsensusSelector()
    c1 = _c("a", "codex", "the answer is 42")
    c2 = _c("b", "gemini", "the answer is 42")
    c3 = _c("c", "codex", "something different entirely")
    # c1 and c2 agree, c3 doesn't
    # c1 score=0.7, c2 score=0.7, c3 score=0.8
    # Without consensus, c3 wins. With consensus bonus, c1/c2 should win.
    winner = sel.select([(c1, _f(0.7)), (c2, _f(0.7)), (c3, _f(0.75))])
    assert winner.id in ("a", "b")  # consensus bonus pushes them above c3
```

**Step 2: Implement**

```python
# ygn-brain/src/ygn_brain/harness/policy.py
"""Refinement policies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ygn_brain.harness.types import Feedback


class RefinementPolicy(ABC):
    @abstractmethod
    def should_continue(self, round: int, best_score: float, history: list[Feedback]) -> bool: ...

    @abstractmethod
    def refine_prompt(self, task: str, feedback: Feedback) -> str: ...


class DefaultPolicy(RefinementPolicy):
    def __init__(self, max_rounds: int = 3, min_score: float = 0.8) -> None:
        self._max_rounds = max_rounds
        self._min_score = min_score

    def should_continue(self, round: int, best_score: float, history: list[Feedback]) -> bool:
        return round < self._max_rounds and best_score < self._min_score

    def refine_prompt(self, task: str, feedback: Feedback) -> str:
        return (
            f"{task}\n\n"
            f"Previous attempt feedback: {feedback.diagnostics}\n"
            f"Score: {feedback.score:.2f}. Please improve."
        )
```

```python
# ygn-brain/src/ygn_brain/harness/selector.py
"""Candidate selection strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter

from ygn_brain.harness.types import Candidate, Feedback


class Selector(ABC):
    @abstractmethod
    def select(self, candidates: list[tuple[Candidate, Feedback]]) -> Candidate: ...


class ConsensusSelector(Selector):
    """Select by score + consensus bonus.

    If 2+ providers produce similar outputs, they get a bonus.
    """

    def __init__(self, consensus_bonus: float = 0.15) -> None:
        self._bonus = consensus_bonus

    def select(self, candidates: list[tuple[Candidate, Feedback]]) -> Candidate:
        if not candidates:
            raise ValueError("No candidates to select from")

        # Group outputs by normalized content
        output_groups: dict[str, list[str]] = {}
        for c, _ in candidates:
            key = c.output.strip().lower()[:200]
            output_groups.setdefault(key, []).append(c.id)

        # Find consensus groups (2+ candidates with same output)
        consensus_ids: set[str] = set()
        for key, ids in output_groups.items():
            if len(ids) >= 2:
                consensus_ids.update(ids)

        # Score with bonus
        scored: list[tuple[float, float, Candidate]] = []
        for c, f in candidates:
            effective_score = f.score
            if c.id in consensus_ids:
                effective_score += self._bonus
            scored.append((effective_score, -c.latency_ms, c))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return scored[0][2]
```

**Step 3: Run tests + commit**

```bash
git add ygn-brain/src/ygn_brain/harness/policy.py ygn-brain/src/ygn_brain/harness/selector.py ygn-brain/tests/test_harness_policy.py
git commit -m "feat(harness): add DefaultPolicy + ConsensusSelector"
```

---

## Task 5: HarnessMemoryStore

**Files:**
- Create: `ygn-brain/src/ygn_brain/harness/memory_store.py`
- Create: `ygn-brain/tests/test_harness_memory.py`

**Step 1: Write the failing tests**

```python
# ygn-brain/tests/test_harness_memory.py
"""Tests for harness memory store."""

from ygn_brain.harness.types import Candidate, Feedback
from ygn_brain.harness.memory_store import HarnessMemoryStore


def test_store_and_recall_pattern():
    store = HarnessMemoryStore()
    c = Candidate(id="c1", provider="codex", model="m", prompt="solve X",
                  output="answer", latency_ms=100, token_count=10)
    f = Feedback(passed=True, score=0.9, diagnostics="ok")
    store.store_pattern("solve math", c, f)

    patterns = store.recall_patterns("solve math")
    assert len(patterns) >= 1
    assert patterns[0]["provider"] == "codex"
    assert patterns[0]["score"] == 0.9


def test_recall_empty():
    store = HarnessMemoryStore()
    patterns = store.recall_patterns("unknown task")
    assert patterns == []
```

**Step 2: Implement**

```python
# ygn-brain/src/ygn_brain/harness/memory_store.py
"""Memory store for capitalizing harness patterns."""

from __future__ import annotations

from ygn_brain.harness.types import Candidate, Feedback
from ygn_brain.memory import MemoryCategory
from ygn_brain.tiered_memory import MemoryTier, TieredMemoryService


class HarnessMemoryStore:
    """Stores winning patterns for reuse in future runs."""

    def __init__(self, memory: TieredMemoryService | None = None) -> None:
        self._memory = memory or TieredMemoryService()

    def store_pattern(
        self, task: str, candidate: Candidate, feedback: Feedback,
    ) -> None:
        key = f"harness:{candidate.id}"
        content = (
            f"task: {task}\n"
            f"provider: {candidate.provider}\n"
            f"model: {candidate.model}\n"
            f"score: {feedback.score}\n"
            f"prompt: {candidate.prompt[:200]}"
        )
        self._memory.store(
            key, content, MemoryCategory.CORE, "harness",
            tier=MemoryTier.COLD,
        )

    def recall_patterns(self, task: str, limit: int = 3) -> list[dict]:
        results = self._memory.recall(task, limit=limit)
        patterns = []
        for r in results:
            if r.key.startswith("harness:"):
                lines = r.content.split("\n")
                pattern = {}
                for line in lines:
                    if ": " in line:
                        k, v = line.split(": ", 1)
                        pattern[k] = float(v) if k == "score" else v
                patterns.append(pattern)
        return patterns
```

**Step 3: Run tests + commit**

```bash
git add ygn-brain/src/ygn_brain/harness/memory_store.py ygn-brain/tests/test_harness_memory.py
git commit -m "feat(harness): add HarnessMemoryStore for pattern capitalization"
```

---

## Task 6: RefinementHarness engine (main loop)

**Files:**
- Create: `ygn-brain/src/ygn_brain/harness/engine.py`
- Create: `ygn-brain/tests/test_harness_engine.py`

**Step 1: Write the failing tests**

```python
# ygn-brain/tests/test_harness_engine.py
"""Tests for the RefinementHarness engine."""

import pytest
from ygn_brain.harness.types import HarnessConfig
from ygn_brain.harness.engine import RefinementHarness
from ygn_brain.harness.candidate import StubCandidateGenerator
from ygn_brain.harness.verifier import TextVerifier
from ygn_brain.harness.policy import DefaultPolicy
from ygn_brain.harness.selector import ConsensusSelector
from ygn_brain.evidence import EvidencePack


@pytest.mark.asyncio
async def test_engine_runs_and_produces_result():
    harness = RefinementHarness(
        generator=StubCandidateGenerator(output="Here is a detailed analysis of the problem with multiple points."),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=2, min_score=0.5),
        selector=ConsensusSelector(),
    )
    config = HarnessConfig(providers=["stub"], candidates_per_provider=2, max_rounds=2, min_score=0.5)
    result = await harness.run("analyze this", config)
    assert result.winner is not None
    assert result.winner.output != ""
    assert result.rounds_used >= 1


@pytest.mark.asyncio
async def test_engine_stops_when_score_reached():
    harness = RefinementHarness(
        generator=StubCandidateGenerator(output="A detailed and structured analysis:\n- Point 1\n- Point 2\n- Point 3"),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=5, min_score=0.3),
        selector=ConsensusSelector(),
    )
    config = HarnessConfig(providers=["stub"], candidates_per_provider=1, max_rounds=5, min_score=0.3)
    result = await harness.run("analyze", config)
    assert result.rounds_used == 1  # Should stop after first round (score > 0.3)


@pytest.mark.asyncio
async def test_engine_traces_to_evidence():
    evidence = EvidencePack(task_description="test", model_id="harness")
    harness = RefinementHarness(
        generator=StubCandidateGenerator(output="A complete analysis with details and structure."),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=1, min_score=0.5),
        selector=ConsensusSelector(),
        evidence=evidence,
    )
    config = HarnessConfig(providers=["stub"], candidates_per_provider=1, max_rounds=1)
    await harness.run("task", config)
    assert len(evidence.entries) > 0
    kinds = [e.kind for e in evidence.entries]
    assert "output" in kinds  # candidate entries use EvidenceKind
```

**Step 2: Implement**

```python
# ygn-brain/src/ygn_brain/harness/engine.py
"""RefinementHarness — the main generate-verify-refine loop."""

from __future__ import annotations

import hashlib

from ygn_brain.evidence import EvidencePack
from ygn_brain.harness.candidate import CandidateGenerator
from ygn_brain.harness.memory_store import HarnessMemoryStore
from ygn_brain.harness.policy import RefinementPolicy
from ygn_brain.harness.selector import Selector
from ygn_brain.harness.types import Candidate, Feedback, HarnessConfig, HarnessResult
from ygn_brain.harness.verifier import Verifier


class RefinementHarness:
    """Poetiq-inspired generate-verify-refine engine.

    Composes: CandidateGenerator, Verifier, RefinementPolicy, Selector, MemoryStore.
    Each iteration traces to EvidencePack.
    """

    def __init__(
        self,
        generator: CandidateGenerator,
        verifier: Verifier,
        policy: RefinementPolicy,
        selector: Selector,
        memory: HarnessMemoryStore | None = None,
        evidence: EvidencePack | None = None,
    ) -> None:
        self._generator = generator
        self._verifier = verifier
        self._policy = policy
        self._selector = selector
        self._memory = memory
        self._evidence = evidence

    async def run(self, task: str, config: HarnessConfig) -> HarnessResult:
        # Recall patterns from memory
        context = ""
        if self._memory:
            patterns = self._memory.recall_patterns(task)
            if patterns:
                context = f"Previous successful patterns:\n{patterns[0]}"

        all_candidates: list[tuple[Candidate, Feedback]] = []
        best_score = 0.0
        current_task = task
        round_num = 0

        while self._policy.should_continue(round_num, best_score, [f for _, f in all_candidates]):
            # Generate candidates
            candidates = await self._generator.generate(current_task, context, config)

            # Verify each candidate
            for candidate in candidates:
                feedback = self._verifier.verify(candidate, task)
                all_candidates.append((candidate, feedback))

                # Trace to evidence
                if self._evidence:
                    self._evidence.add(
                        phase="harness",
                        kind="output",
                        data={
                            "round": round_num,
                            "candidate_id": candidate.id,
                            "provider": candidate.provider,
                            "output_hash": hashlib.sha256(
                                candidate.output.encode()
                            ).hexdigest()[:16],
                            "score": feedback.score,
                            "passed": feedback.passed,
                        },
                    )

                if feedback.score > best_score:
                    best_score = feedback.score

            round_num += 1

            # Refine prompt if continuing
            if self._policy.should_continue(round_num, best_score, [f for _, f in all_candidates]):
                worst = min(all_candidates, key=lambda x: x[1].score)
                current_task = self._policy.refine_prompt(task, worst[1])

        # Select winner
        winner = self._selector.select(all_candidates)
        winner_feedback = next(f for c, f in all_candidates if c.id == winner.id)

        # Store winning pattern
        if self._memory:
            self._memory.store_pattern(task, winner, winner_feedback)

        # Trace selection
        if self._evidence:
            self._evidence.add(
                phase="harness",
                kind="decision",
                data={
                    "action": "selection",
                    "winner_id": winner.id,
                    "winner_score": winner_feedback.score,
                    "total_candidates": len(all_candidates),
                    "rounds_used": round_num,
                },
            )

        return HarnessResult(
            winner=winner,
            feedback=winner_feedback,
            rounds_used=round_num,
            total_candidates=len(all_candidates),
        )
```

**Step 3: Run tests + commit**

```bash
git add ygn-brain/src/ygn_brain/harness/engine.py ygn-brain/tests/test_harness_engine.py
git commit -m "feat(harness): add RefinementHarness engine (main generate-verify-refine loop)"
```

---

## Task 7: Harness exports + MCP tool + drift fixes

**Files:**
- Modify: `ygn-brain/src/ygn_brain/harness/__init__.py`
- Modify: `ygn-brain/src/ygn_brain/__init__.py`
- Modify: `ygn-brain/src/ygn_brain/mcp_server.py` (line 164: fix version, add tool)
- Modify: `README.md` (line 3: fix version, lines 128-134: fix test counts)

**Step 1: Update harness __init__.py exports**

```python
# ygn-brain/src/ygn_brain/harness/__init__.py
"""Refinement Harness — Poetiq-inspired generate-verify-refine engine."""

from .candidate import CandidateGenerator, MultiProviderGenerator, StubCandidateGenerator
from .engine import RefinementHarness
from .memory_store import HarnessMemoryStore
from .policy import DefaultPolicy, RefinementPolicy
from .selector import ConsensusSelector, Selector
from .types import POETIQ_PRESET, Candidate, Feedback, HarnessConfig, HarnessResult
from .verifier import CommandVerifier, TextVerifier, Verifier

__all__ = [
    "CandidateGenerator", "MultiProviderGenerator", "StubCandidateGenerator",
    "RefinementHarness",
    "HarnessMemoryStore",
    "DefaultPolicy", "RefinementPolicy",
    "ConsensusSelector", "Selector",
    "POETIQ_PRESET", "Candidate", "Feedback", "HarnessConfig", "HarnessResult",
    "CommandVerifier", "TextVerifier", "Verifier",
]
```

**Step 2: Fix MCP serverInfo.version drift**

In `mcp_server.py` line 164, replace:
```python
"version": "0.3.0",
```
with:
```python
"version": __version__,
```

Add at top of file: `from ygn_brain import __version__`

**Step 3: Add `orchestrate_refined` MCP tool**

Add 7th tool to `_TOOLS` list and handler.

**Step 4: Fix README.md drifts**

- Line 3: `v0.2.1` → `v0.5.0`
- Lines 128-134: Update test counts to current (373 Rust, 410 Python, 783 total)

**Step 5: Run full test suite + ruff + commit**

```bash
cd ygn-brain && ruff check . --fix && ruff format . && python -m pytest -q
cd ygn-core && cargo test --target x86_64-pc-windows-msvc 2>&1 | grep "test result"

git add -A
git commit -m "feat(harness): exports, orchestrate_refined MCP tool, fix version drifts"
```

---

## Task 8: E2E tests (real CLI)

**Files:**
- Create: `ygn-brain/tests/test_harness_e2e.py`

**Step 1: Write E2E tests**

```python
# ygn-brain/tests/test_harness_e2e.py
"""E2E tests for Refinement Harness with real CLI providers.

Requires: Codex CLI + Gemini CLI installed.
Run: pytest tests/test_harness_e2e.py -v -m e2e
"""

import pytest
from ygn_brain.harness.engine import RefinementHarness
from ygn_brain.harness.candidate import MultiProviderGenerator
from ygn_brain.harness.verifier import TextVerifier
from ygn_brain.harness.policy import DefaultPolicy
from ygn_brain.harness.selector import ConsensusSelector
from ygn_brain.harness.types import HarnessConfig
from ygn_brain.evidence import EvidencePack


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_gemini_single_provider():
    """Gemini CLI, single provider, 2 rounds."""
    harness = RefinementHarness(
        generator=MultiProviderGenerator(),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=2, min_score=0.5),
        selector=ConsensusSelector(),
    )
    config = HarnessConfig(
        providers=["gemini"],
        candidates_per_provider=1,
        max_rounds=2,
        min_score=0.5,
    )
    result = await harness.run("Explain what a refinement loop is in 3 sentences.", config)
    assert result.winner.output != ""
    assert result.feedback.score > 0.0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_ensemble_codex_gemini():
    """Ensemble: Codex + Gemini, consensus selection."""
    evidence = EvidencePack(task_description="e2e-ensemble", model_id="harness")
    harness = RefinementHarness(
        generator=MultiProviderGenerator(),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=2, min_score=0.6),
        selector=ConsensusSelector(),
        evidence=evidence,
    )
    config = HarnessConfig(
        providers=["gemini", "codex"],
        candidates_per_provider=1,
        max_rounds=2,
        min_score=0.6,
        ensemble=True,
    )
    result = await harness.run("What is 2+2? Answer in one word.", config)
    assert result.winner.output != ""
    assert result.total_candidates >= 2


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_evidence_export():
    """Evidence trace: JSONL valid + Merkle root."""
    evidence = EvidencePack(task_description="e2e-evidence", model_id="harness")
    harness = RefinementHarness(
        generator=MultiProviderGenerator(),
        verifier=TextVerifier(),
        policy=DefaultPolicy(max_rounds=1, min_score=0.5),
        selector=ConsensusSelector(),
        evidence=evidence,
    )
    config = HarnessConfig(providers=["gemini"], candidates_per_provider=1, max_rounds=1)
    await harness.run("Say hello", config)
    evidence.save()
    assert len(evidence.entries) > 0
    assert len(evidence.merkle_root_hash()) > 0
```

**Step 2: Run (skip if no CLI)**

```bash
cd ygn-brain && python -m pytest tests/test_harness_e2e.py -v -m e2e
```

If CLI not available, tests skip. If available, should pass.

**Step 3: Commit**

```bash
git add ygn-brain/tests/test_harness_e2e.py
git commit -m "test(harness): add E2E tests for real CLI providers (Codex + Gemini)"
```

---

## Task 9: Final docs update

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md`
- Modify: `memory-bank/progress.md`, `activeContext.md`, `decisionLog.md`

Update all docs with Refinement Harness feature, test counts, architecture description.

```bash
git add -A
git commit -m "docs: Refinement Harness release notes"
```

---

## Full test suite verification

```bash
# Python
cd ygn-brain && python -m pytest -v -k "not e2e"
# Expected: ~430+ tests PASSED

# E2E (if CLI available)
cd ygn-brain && python -m pytest tests/test_harness_e2e.py -v -m e2e

# Rust
cd ygn-core && cargo test --target x86_64-pc-windows-msvc
# Expected: 373 tests PASSED

# Dashboard
cd ygn-dash && bun run build
```

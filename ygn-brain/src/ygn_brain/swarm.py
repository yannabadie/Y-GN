"""Hybrid Swarm Engine — multi-agent execution modes."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .provider import LLMProvider


class SwarmMode(StrEnum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    RED_BLUE = "red_blue"
    PING_PONG = "ping_pong"
    LEAD_SUPPORT = "lead_support"
    SPECIALIST = "specialist"


class TaskComplexity(StrEnum):
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXPERT = "expert"


@dataclass
class TaskAnalysis:
    """Result of analyzing a task's complexity and requirements."""

    complexity: TaskComplexity
    domains: list[str]
    suggested_mode: SwarmMode


@dataclass
class SwarmResult:
    """Output from a swarm execution."""

    mode: SwarmMode
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Keyword-based heuristics for task analysis
# ---------------------------------------------------------------------------

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "code": ["code", "function", "class", "debug", "refactor", "implement", "program"],
    "math": ["calculate", "equation", "formula", "prove", "theorem", "math"],
    "writing": ["write", "essay", "article", "draft", "summarize", "story"],
    "research": ["research", "analyze", "compare", "investigate", "study", "review"],
    "data": ["data", "dataset", "csv", "json", "database", "query", "sql"],
    "design": ["design", "architecture", "ui", "ux", "layout", "wireframe"],
}


class TaskAnalyzer:
    """Analyzes input to suggest complexity and swarm mode."""

    def analyze(self, user_input: str) -> TaskAnalysis:
        """Determine task complexity, domains, and suggested mode."""
        lower = user_input.lower()
        words = lower.split()
        word_count = len(words)

        # Detect domains
        domains: list[str] = []
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                domains.append(domain)
        if not domains:
            domains = ["general"]

        # Determine complexity based on heuristics
        complexity = self._assess_complexity(lower, word_count, domains)

        # Suggest mode based on complexity and domain count
        suggested_mode = self._suggest_mode(complexity, domains)

        return TaskAnalysis(
            complexity=complexity,
            domains=domains,
            suggested_mode=suggested_mode,
        )

    def _assess_complexity(self, text: str, word_count: int, domains: list[str]) -> TaskComplexity:
        """Heuristic complexity assessment."""
        if word_count <= 3:
            return TaskComplexity.TRIVIAL
        if word_count <= 10 and len(domains) <= 1:
            return TaskComplexity.SIMPLE
        if len(domains) >= 3 or word_count > 50:
            return TaskComplexity.EXPERT
        if len(domains) >= 2 or word_count > 25:
            return TaskComplexity.COMPLEX
        return TaskComplexity.MODERATE

    def _suggest_mode(self, complexity: TaskComplexity, domains: list[str]) -> SwarmMode:
        """Suggest an execution mode based on analysis."""
        if complexity == TaskComplexity.TRIVIAL:
            return SwarmMode.SEQUENTIAL
        if complexity == TaskComplexity.SIMPLE:
            return SwarmMode.SEQUENTIAL
        if complexity == TaskComplexity.MODERATE:
            return SwarmMode.LEAD_SUPPORT
        if complexity == TaskComplexity.EXPERT:
            return SwarmMode.SPECIALIST
        # COMPLEX with multiple domains => parallel
        if len(domains) >= 2:
            return SwarmMode.PARALLEL
        return SwarmMode.RED_BLUE


# ---------------------------------------------------------------------------
# Executor interface and implementations
# ---------------------------------------------------------------------------


class SwarmExecutor(ABC):
    """Abstract base class for swarm executors."""

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> SwarmResult:
        """Execute the task in a specific swarm mode."""


class ParallelExecutor(SwarmExecutor):
    """Stub: simulates parallel multi-agent execution."""

    def execute(self, context: dict[str, Any]) -> SwarmResult:
        user_input = context.get("user_input", "")
        return SwarmResult(
            mode=SwarmMode.PARALLEL,
            output=f"[parallel] Processed: {user_input}",
            metadata={"agents": 3, "strategy": "fan-out-fan-in"},
        )


class SequentialExecutor(SwarmExecutor):
    """Stub: simulates sequential single-agent execution."""

    def execute(self, context: dict[str, Any]) -> SwarmResult:
        user_input = context.get("user_input", "")
        return SwarmResult(
            mode=SwarmMode.SEQUENTIAL,
            output=f"[sequential] Processed: {user_input}",
            metadata={"agents": 1, "strategy": "chain"},
        )


class SpecialistExecutor(SwarmExecutor):
    """Stub: simulates specialist-routed execution."""

    def execute(self, context: dict[str, Any]) -> SwarmResult:
        user_input = context.get("user_input", "")
        domains = context.get("domains", ["general"])
        return SwarmResult(
            mode=SwarmMode.SPECIALIST,
            output=f"[specialist] Processed: {user_input}",
            metadata={"agents": len(domains), "domains": domains, "strategy": "expert-routing"},
        )


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

_DEFAULT_EXECUTORS: dict[SwarmMode, SwarmExecutor] = {
    SwarmMode.PARALLEL: ParallelExecutor(),
    SwarmMode.SEQUENTIAL: SequentialExecutor(),
    SwarmMode.SPECIALIST: SpecialistExecutor(),
    # Unmapped modes fall back to sequential
}


class SwarmEngine:
    """Routes tasks to the appropriate executor based on analysis."""

    def __init__(
        self,
        executors: dict[SwarmMode, SwarmExecutor] | None = None,
        analyzer: TaskAnalyzer | None = None,
    ) -> None:
        self._executors = executors if executors is not None else dict(_DEFAULT_EXECUTORS)
        self._analyzer = analyzer if analyzer is not None else TaskAnalyzer()
        self._fallback: SwarmExecutor = SequentialExecutor()

    def analyze(self, user_input: str) -> TaskAnalysis:
        """Analyze a task without executing it."""
        return self._analyzer.analyze(user_input)

    def run(self, user_input: str) -> SwarmResult:
        """Analyze then execute."""
        analysis = self._analyzer.analyze(user_input)
        context: dict[str, Any] = {
            "user_input": user_input,
            "complexity": analysis.complexity,
            "domains": analysis.domains,
            "suggested_mode": analysis.suggested_mode,
        }
        executor = self._executors.get(analysis.suggested_mode, self._fallback)
        return executor.execute(context)

    async def execute_with_provider(
        self,
        task: str,
        provider: LLMProvider,
    ) -> SwarmResult:
        """Execute a task using a real LLM provider.

        Analyzes the task to determine complexity and mode, then delegates to
        mode-specific LLM execution logic:

        - **Parallel**: sends multiple prompts concurrently via ``asyncio.gather``.
        - **Sequential**: chains LLM calls so the output of one feeds into the next.
        - **Specialist**: uses a focused domain prompt for expert-level tasks.
        - All other modes fall back to a single LLM call.

        Existing :meth:`run` is unaffected — this is a new async path.
        """
        analysis = self._analyzer.analyze(task)
        mode = analysis.suggested_mode

        if mode == SwarmMode.PARALLEL:
            return await self._run_parallel(task, analysis, provider)
        if mode == SwarmMode.SEQUENTIAL:
            return await self._run_sequential(task, analysis, provider)
        if mode == SwarmMode.SPECIALIST:
            return await self._run_specialist(task, analysis, provider)
        # Fallback: single LLM call for unmapped modes
        return await self._run_single(task, mode, provider)

    # ------------------------------------------------------------------
    # Provider-backed mode implementations
    # ------------------------------------------------------------------

    @staticmethod
    async def _run_parallel(
        task: str,
        analysis: TaskAnalysis,
        provider: LLMProvider,
    ) -> SwarmResult:
        """Fan-out the task to multiple agents concurrently."""
        from .provider import ChatMessage, ChatRequest, ChatRole

        model = getattr(provider, "_model", None) or provider.name()
        prompts = [
            f"As a {domain} specialist, address the following task:\n{task}"
            for domain in analysis.domains
        ]

        async def _call(prompt: str) -> str:
            resp = await provider.chat(
                ChatRequest(
                    model=model,
                    messages=[
                        ChatMessage(role=ChatRole.SYSTEM, content="You are a specialist agent."),
                        ChatMessage(role=ChatRole.USER, content=prompt),
                    ],
                )
            )
            return resp.content

        results = await asyncio.gather(*[_call(p) for p in prompts])
        combined = "\n---\n".join(results)
        return SwarmResult(
            mode=SwarmMode.PARALLEL,
            output=combined,
            metadata={
                "agents": len(prompts),
                "domains": analysis.domains,
                "strategy": "fan-out-fan-in",
            },
        )

    @staticmethod
    async def _run_sequential(
        task: str,
        analysis: TaskAnalysis,  # noqa: ARG004
        provider: LLMProvider,
    ) -> SwarmResult:
        """Chain LLM calls — each step's output feeds into the next."""
        from .provider import ChatMessage, ChatRequest, ChatRole

        model = getattr(provider, "_model", None) or provider.name()
        steps = ["understand", "plan", "execute"]
        current = task
        for step in steps:
            resp = await provider.chat(
                ChatRequest(
                    model=model,
                    messages=[
                        ChatMessage(
                            role=ChatRole.SYSTEM,
                            content=f"You are performing step '{step}' in a sequential pipeline.",
                        ),
                        ChatMessage(role=ChatRole.USER, content=current),
                    ],
                )
            )
            current = resp.content
        return SwarmResult(
            mode=SwarmMode.SEQUENTIAL,
            output=current,
            metadata={
                "agents": 1,
                "steps": steps,
                "strategy": "chain",
            },
        )

    @staticmethod
    async def _run_specialist(
        task: str,
        analysis: TaskAnalysis,
        provider: LLMProvider,
    ) -> SwarmResult:
        """Use a focused domain prompt for expert-level tasks."""
        from .provider import ChatMessage, ChatRequest, ChatRole

        model = getattr(provider, "_model", None) or provider.name()
        domain_list = ", ".join(analysis.domains)
        resp = await provider.chat(
            ChatRequest(
                model=model,
                messages=[
                    ChatMessage(
                        role=ChatRole.SYSTEM,
                        content=(
                            f"You are an expert specialist in: {domain_list}. "
                            "Provide a thorough, expert-level response."
                        ),
                    ),
                    ChatMessage(role=ChatRole.USER, content=task),
                ],
            )
        )
        return SwarmResult(
            mode=SwarmMode.SPECIALIST,
            output=resp.content,
            metadata={
                "agents": len(analysis.domains),
                "domains": analysis.domains,
                "strategy": "expert-routing",
            },
        )

    @staticmethod
    async def _run_single(
        task: str,
        mode: SwarmMode,
        provider: LLMProvider,
    ) -> SwarmResult:
        """Fallback: single LLM call for any unmapped mode."""
        from .provider import ChatMessage, ChatRequest, ChatRole

        model = getattr(provider, "_model", None) or provider.name()
        resp = await provider.chat(
            ChatRequest(
                model=model,
                messages=[
                    ChatMessage(
                        role=ChatRole.SYSTEM,
                        content=f"You are operating in '{mode}' mode.",
                    ),
                    ChatMessage(role=ChatRole.USER, content=task),
                ],
            )
        )
        return SwarmResult(
            mode=mode,
            output=resp.content,
            metadata={"agents": 1, "strategy": mode.value},
        )

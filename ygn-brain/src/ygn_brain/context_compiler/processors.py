"""Context compiler processors — named, composable pipeline stages."""

from __future__ import annotations

from typing import Any, Protocol

from ..memory import MemoryService
from .artifact_store import ArtifactStore
from .session import Session
from .token_budget import estimate_tokens
from .working_context import WorkingContext


class Processor(Protocol):
    """Named, composable context processor."""

    name: str

    def process(self, session: Session, ctx: WorkingContext, budget: int) -> WorkingContext: ...


class HistorySelector:
    """Select recent turns, keep first + last N, drop middle if over budget."""

    name = "history_selector"

    def __init__(self, keep_first: int = 2, keep_last: int = 5) -> None:
        self._keep_first = keep_first
        self._keep_last = keep_last

    def process(self, session: Session, ctx: WorkingContext, budget: int) -> WorkingContext:
        conv_events = [
            e for e in session.event_log.events
            if e.kind in ("user_input", "phase_result")
        ]
        history: list[dict[str, Any]] = []
        for evt in conv_events:
            role = evt.data.get("role", "user")
            content = evt.data.get("content", evt.data.get("text", ""))
            history.append({"role": role, "content": content})

        if not history:
            return ctx

        total = len(history)
        if total <= self._keep_first + self._keep_last:
            selected = history
        else:
            selected = history[: self._keep_first] + history[total - self._keep_last :]

        token_count = sum(estimate_tokens(h["content"]) for h in selected)
        return WorkingContext(
            system_prompt=ctx.system_prompt,
            history=selected,
            memory_hits=ctx.memory_hits,
            artifact_refs=ctx.artifact_refs,
            tool_results=ctx.tool_results,
            token_count=token_count + estimate_tokens(ctx.system_prompt),
            budget=budget,
        )


class Compactor:
    """Merge consecutive same-role messages, trim whitespace."""

    name = "compactor"

    def process(self, session: Session, ctx: WorkingContext, budget: int) -> WorkingContext:
        if not ctx.history:
            return ctx

        merged: list[dict[str, Any]] = []
        for msg in ctx.history:
            content = msg["content"].strip()
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] += "\n" + content
            else:
                merged.append({"role": msg["role"], "content": content})

        token_count = sum(estimate_tokens(h["content"]) for h in merged)
        return WorkingContext(
            system_prompt=ctx.system_prompt,
            history=merged,
            memory_hits=ctx.memory_hits,
            artifact_refs=ctx.artifact_refs,
            tool_results=ctx.tool_results,
            token_count=token_count + estimate_tokens(ctx.system_prompt),
            budget=budget,
        )


class MemoryPreloader:
    """Query memory service, inject top-K relevant memories into context."""

    name = "memory_preloader"

    def __init__(self, memory_service: MemoryService, top_k: int = 5) -> None:
        self._memory = memory_service
        self._top_k = top_k

    def process(self, session: Session, ctx: WorkingContext, budget: int) -> WorkingContext:
        user_events = session.event_log.filter(["user_input"])
        if not user_events:
            return ctx
        query = user_events[-1].data.get("text", user_events[-1].data.get("content", ""))
        if not query:
            return ctx

        entries = self._memory.recall(query, limit=self._top_k)
        hits = [{"key": e.key, "content": e.content, "category": e.category} for e in entries]

        extra_tokens = sum(estimate_tokens(h["content"]) for h in hits)
        return WorkingContext(
            system_prompt=ctx.system_prompt,
            history=ctx.history,
            memory_hits=hits,
            artifact_refs=ctx.artifact_refs,
            tool_results=ctx.tool_results,
            token_count=ctx.token_count + extra_tokens,
            budget=budget,
        )


class ArtifactAttacher:
    """Replace large payloads with artifact handles + summaries."""

    name = "artifact_attacher"

    def __init__(self, artifact_store: ArtifactStore, threshold_bytes: int = 1024) -> None:
        self._store = artifact_store
        self._threshold = threshold_bytes

    def process(self, session: Session, ctx: WorkingContext, budget: int) -> WorkingContext:
        remaining_results: list[dict[str, Any]] = []
        new_refs: list[dict[str, Any]] = list(ctx.artifact_refs)
        saved_tokens = 0

        for tr in ctx.tool_results:
            result_text = tr.get("result", "")
            result_bytes = result_text.encode("utf-8") if isinstance(result_text, str) else result_text
            if len(result_bytes) >= self._threshold:
                handle = self._store.store(
                    result_bytes,
                    source=f"tool:{tr.get('tool', 'unknown')}",
                    mime_type="text/plain",
                )
                new_refs.append({
                    "handle": handle.artifact_id,
                    "summary": handle.summary,
                    "size_bytes": handle.size_bytes,
                    "source": handle.source,
                })
                saved_tokens += estimate_tokens(result_text)
                session.record(
                    "artifact_stored",
                    {"handle": handle.artifact_id, "source": handle.source, "size_bytes": handle.size_bytes},
                    token_estimate=10,
                )
            else:
                remaining_results.append(tr)

        ref_tokens = sum(estimate_tokens(r.get("summary", "")) for r in new_refs)
        return WorkingContext(
            system_prompt=ctx.system_prompt,
            history=ctx.history,
            memory_hits=ctx.memory_hits,
            artifact_refs=new_refs,
            tool_results=remaining_results,
            token_count=ctx.token_count - saved_tokens + ref_tokens,
            budget=budget,
        )


class ContextCompiler:
    """Runs processors in order to produce a WorkingContext from a Session."""

    def __init__(self, processors: list[Processor] | None = None) -> None:
        self._processors: list[Processor] = processors or []

    def add_processor(self, processor: Processor) -> None:
        self._processors.append(processor)

    def compile(
        self, session: Session, budget: int, system_prompt: str = ""
    ) -> WorkingContext:
        ctx = WorkingContext(
            system_prompt=system_prompt,
            history=[],
            memory_hits=[],
            artifact_refs=[],
            tool_results=[],
            token_count=estimate_tokens(system_prompt),
            budget=budget,
        )
        for proc in self._processors:
            ctx = proc.process(session, ctx, budget)
        return ctx

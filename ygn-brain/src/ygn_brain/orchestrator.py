"""Lightweight orchestrator (Mediator pattern — replaces OrchestratorV7 god-object)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from .context import ContextBuilder
from .evidence import EvidencePack
from .fsm import FSMState, Phase
from .guard import GuardPipeline
from .hivemind import HiveMindPipeline
from .memory import MemoryService
from .provider_factory import ProviderFactory

if TYPE_CHECKING:
    from .provider import LLMProvider
    from .provider_router import ProviderRouter


class Orchestrator:
    """Orchestrator that drives the HiveMind 7-phase pipeline with guard and memory."""

    def __init__(
        self,
        guard_pipeline: GuardPipeline | None = None,
        memory_service: MemoryService | None = None,
        provider: LLMProvider | None = None,
        provider_router: ProviderRouter | None = None,
    ) -> None:
        self.state = FSMState()
        self.evidence = EvidencePack(session_id=uuid.uuid4().hex[:12])
        self._guard_pipeline = guard_pipeline if guard_pipeline is not None else GuardPipeline()
        self._memory_service = memory_service
        self._context_builder = ContextBuilder()
        self._hivemind = HiveMindPipeline()
        # Use factory to resolve provider if none given explicitly
        self._provider = provider if provider is not None else ProviderFactory.create()
        self._provider_router = provider_router

    def run(self, user_input: str) -> dict[str, Any]:
        """Execute a full pipeline pass.

        Returns dict with ``result`` and ``session_id`` keys (backward-compatible).
        """
        # Build execution context (guard + memory + evidence)
        ctx = self._context_builder.build(
            user_input=user_input,
            session_id=self.evidence.session_id,
            memory_service=self._memory_service,
            guard_pipeline=self._guard_pipeline,
        )

        # If guard blocks, short-circuit
        if not ctx.guard_result.allowed:
            self.evidence = ctx.evidence
            self.evidence.add(
                "guard",
                "decision",
                {
                    "blocked": True,
                    "threat_level": ctx.guard_result.threat_level,
                    "reason": ctx.guard_result.reason,
                },
            )
            return {
                "result": f"Blocked: {ctx.guard_result.reason}",
                "session_id": self.evidence.session_id,
                "blocked": True,
            }

        # Run HiveMind pipeline
        results = self._hivemind.run(user_input, ctx.evidence)

        # Update internal state by walking FSM through all phases
        self.state = FSMState()
        for phase in [
            Phase.DIAGNOSIS,
            Phase.ANALYSIS,
            Phase.PLANNING,
            Phase.EXECUTION,
            Phase.VALIDATION,
            Phase.SYNTHESIS,
            Phase.COMPLETE,
        ]:
            self.state = self.state.transition(phase)

        # Extract final result from synthesis phase
        synthesis_results = [r for r in results if r.phase == "synthesis"]
        if synthesis_results:
            final = synthesis_results[0].data.get("final", "")
        else:
            final = f"Processed: {user_input}"

        self.evidence = ctx.evidence

        return {
            "result": final,
            "session_id": self.evidence.session_id,
        }

    async def run_async(self, user_input: str) -> dict[str, Any]:
        """Execute a full pipeline pass using the LLM provider.

        This async counterpart of :meth:`run` delegates cognitive phases to a
        real LLM via the provider set at construction time.  The provider is
        always set (via ``ProviderFactory.create()`` if none was given).

        Returns dict with ``result`` and ``session_id`` keys.
        """

        # Build execution context (guard + memory + evidence)
        ctx = self._context_builder.build(
            user_input=user_input,
            session_id=self.evidence.session_id,
            memory_service=self._memory_service,
            guard_pipeline=self._guard_pipeline,
        )

        # If guard blocks, short-circuit
        if not ctx.guard_result.allowed:
            self.evidence = ctx.evidence
            self.evidence.add(
                "guard",
                "decision",
                {
                    "blocked": True,
                    "threat_level": ctx.guard_result.threat_level,
                    "reason": ctx.guard_result.reason,
                },
            )
            return {
                "result": f"Blocked: {ctx.guard_result.reason}",
                "session_id": self.evidence.session_id,
                "blocked": True,
            }

        # Run HiveMind pipeline with provider
        results = await self._hivemind.run_with_provider(user_input, ctx.evidence, self._provider)

        # Update internal state
        self.state = FSMState()
        for phase in [
            Phase.DIAGNOSIS,
            Phase.ANALYSIS,
            Phase.PLANNING,
            Phase.EXECUTION,
            Phase.VALIDATION,
            Phase.SYNTHESIS,
            Phase.COMPLETE,
        ]:
            self.state = self.state.transition(phase)

        # Extract final result
        synthesis_results = [r for r in results if r.phase == "synthesis"]
        if synthesis_results:
            final = synthesis_results[0].data.get("final", "")
        else:
            final = f"Processed: {user_input}"

        self.evidence = ctx.evidence

        return {
            "result": final,
            "session_id": self.evidence.session_id,
        }

    def run_compiled(
        self,
        user_input: str,
        budget: int,
        system_prompt: str = "You are a helpful AI assistant.",
        artifact_store: object | None = None,
    ) -> dict[str, Any]:
        """Execute a pipeline pass using the context compiler.

        Creates a Session, compiles a WorkingContext within the token budget,
        then runs the HiveMind pipeline.
        """
        from .context_compiler.processors import (
            ArtifactAttacher,
            Compactor,
            ContextCompiler,
            HistorySelector,
            MemoryPreloader,
        )
        from .context_compiler.session import Session

        # 1. Create session
        session = Session(session_id=self.evidence.session_id)
        token_est = len(user_input.split()) * 2
        session.record("user_input", {"text": user_input}, token_estimate=token_est)

        # 2. Guard check
        guard_result = self._guard_pipeline.evaluate(user_input)
        session.record(
            "guard_decision",
            {"allowed": guard_result.allowed, "threat_level": guard_result.threat_level},
            token_estimate=5,
        )
        if not guard_result.allowed:
            self.evidence = session.to_evidence_pack()
            return {
                "result": f"Blocked: {guard_result.reason}",
                "session_id": session.session_id,
                "blocked": True,
            }

        # 3. Build processor pipeline
        processors: list = [HistorySelector(), Compactor()]
        if self._memory_service:
            processors.append(MemoryPreloader(memory_service=self._memory_service))
        if artifact_store is not None:
            from .context_compiler.artifact_store import ArtifactStore as ArtifactStoreABC

            if isinstance(artifact_store, ArtifactStoreABC):
                processors.append(ArtifactAttacher(artifact_store=artifact_store))

        compiler = ContextCompiler(processors=processors)
        working_ctx = compiler.compile(session, budget=budget, system_prompt=system_prompt)

        # 4. Run HiveMind pipeline
        results = self._hivemind.run(user_input, session.evidence)

        # 5. Update state
        self.state = FSMState()
        for phase in [
            Phase.DIAGNOSIS,
            Phase.ANALYSIS,
            Phase.PLANNING,
            Phase.EXECUTION,
            Phase.VALIDATION,
            Phase.SYNTHESIS,
            Phase.COMPLETE,
        ]:
            self.state = self.state.transition(phase)

        synthesis_results = [r for r in results if r.phase == "synthesis"]
        final = (
            synthesis_results[0].data.get("final", "")
            if synthesis_results
            else f"Processed: {user_input}"
        )

        self.evidence = session.to_evidence_pack()
        return {
            "result": final,
            "session_id": session.session_id,
            "budget_used": working_ctx.token_count,
            "within_budget": working_ctx.is_within_budget(),
        }

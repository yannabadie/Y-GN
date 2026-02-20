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
        self._provider = provider
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
        real LLM via the provider set at construction time.  Raises
        ``RuntimeError`` if no provider was configured.

        Returns dict with ``result`` and ``session_id`` keys.
        """
        if self._provider is None:
            msg = "run_async requires a provider — pass one to Orchestrator()"
            raise RuntimeError(msg)

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
        results = await self._hivemind.run_with_provider(
            user_input, ctx.evidence, self._provider
        )

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

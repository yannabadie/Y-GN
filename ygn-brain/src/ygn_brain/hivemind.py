"""HiveMind 7-phase pipeline — structured cognitive execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .evidence import EvidencePack
from .fsm import FSMState, Phase

if TYPE_CHECKING:
    from .provider import ChatResponse, LLMProvider


@dataclass
class PhaseResult:
    """Output from a single pipeline phase."""

    phase: str
    data: dict[str, Any]
    confidence: float


class HiveMindPipeline:
    """Executes the 7-phase HiveMind pipeline, producing evidence along the way."""

    def run(self, user_input: str, evidence: EvidencePack) -> list[PhaseResult]:
        """Run all 7 phases and return results with evidence side-effects."""
        fsm = FSMState()
        results: list[PhaseResult] = []

        # Phase 1 — Diagnosis: understand the input
        fsm = fsm.transition(Phase.DIAGNOSIS)
        diag_data: dict[str, Any] = {
            "user_input": user_input,
            "input_length": len(user_input),
            "word_count": len(user_input.split()),
        }
        evidence.add("diagnosis", "input", diag_data)
        results.append(PhaseResult(phase="diagnosis", data=diag_data, confidence=1.0))

        # Phase 2 — Analysis: determine strategy
        fsm = fsm.transition(Phase.ANALYSIS)
        strategy = self._determine_strategy(user_input)
        analysis_data: dict[str, Any] = {"strategy": strategy}
        evidence.add("analysis", "decision", analysis_data)
        results.append(PhaseResult(phase="analysis", data=analysis_data, confidence=0.9))

        # Phase 3 — Planning: create execution plan
        fsm = fsm.transition(Phase.PLANNING)
        plan = self._create_plan(user_input, strategy)
        plan_data: dict[str, Any] = {"plan": plan}
        evidence.add("planning", "decision", plan_data)
        results.append(PhaseResult(phase="planning", data=plan_data, confidence=0.85))

        # Phase 4 — Execution: run the plan (stub — placeholder for tool calls)
        fsm = fsm.transition(Phase.EXECUTION)
        exec_output = self._execute_plan(plan)
        exec_data: dict[str, Any] = {"output": exec_output}
        evidence.add("execution", "output", exec_data)
        results.append(PhaseResult(phase="execution", data=exec_data, confidence=0.8))

        # Phase 5 — Validation: check results
        fsm = fsm.transition(Phase.VALIDATION)
        valid = self._validate(exec_output)
        val_data: dict[str, Any] = {"passed": valid, "output": exec_output}
        evidence.add("validation", "decision", val_data)
        val_confidence = 0.9 if valid else 0.4
        results.append(PhaseResult(phase="validation", data=val_data, confidence=val_confidence))

        # Phase 6 — Synthesis: consolidate output
        fsm = fsm.transition(Phase.SYNTHESIS)
        final = self._synthesize(exec_output)
        synth_data: dict[str, Any] = {"final": final}
        evidence.add("synthesis", "output", synth_data)
        results.append(PhaseResult(phase="synthesis", data=synth_data, confidence=0.95))

        # Phase 7 — Complete: finalize evidence
        fsm = fsm.transition(Phase.COMPLETE)
        complete_data: dict[str, Any] = {"status": "complete", "phases_run": len(results)}
        evidence.add("complete", "output", complete_data)
        results.append(PhaseResult(phase="complete", data=complete_data, confidence=1.0))

        return results

    # ------------------------------------------------------------------
    # Internal helpers (stub implementations)
    # ------------------------------------------------------------------

    def _determine_strategy(self, user_input: str) -> str:
        """Choose a processing strategy based on input characteristics."""
        if len(user_input.split()) <= 3:
            return "direct"
        if "?" in user_input:
            return "question_answering"
        return "general"

    def _create_plan(self, user_input: str, strategy: str) -> dict[str, Any]:
        """Build an execution plan."""
        return {
            "strategy": strategy,
            "steps": [
                {"action": "process", "input": user_input},
                {"action": "respond"},
            ],
        }

    def _execute_plan(self, plan: dict[str, Any]) -> str:
        """Execute a plan (stub: returns processed marker)."""
        steps = plan.get("steps", [])
        if steps:
            user_input = steps[0].get("input", "")
            return f"Processed: {user_input}"
        return "Processed: (empty)"

    def _validate(self, output: str) -> bool:
        """Validate execution output."""
        return len(output) > 0

    def _synthesize(self, output: str) -> str:
        """Consolidate the final output."""
        return output

    # ------------------------------------------------------------------
    # Provider-backed async pipeline
    # ------------------------------------------------------------------

    async def run_with_provider(
        self,
        user_input: str,
        evidence: EvidencePack,
        provider: LLMProvider,
    ) -> list[PhaseResult]:
        """Run all 7 phases using a real LLM provider for cognitive steps.

        This is the async counterpart of :meth:`run`.  Non-LLM phases
        (diagnosis, validation, complete) keep their deterministic logic;
        analysis, planning, execution, and synthesis delegate to *provider*.
        """

        fsm = FSMState()
        results: list[PhaseResult] = []
        model = "default"

        # Phase 1 — Diagnosis (deterministic — no LLM needed)
        fsm = fsm.transition(Phase.DIAGNOSIS)
        diag_data: dict[str, Any] = {
            "user_input": user_input,
            "input_length": len(user_input),
            "word_count": len(user_input.split()),
        }
        evidence.add("diagnosis", "input", diag_data)
        results.append(PhaseResult(phase="diagnosis", data=diag_data, confidence=1.0))

        # Phase 2 — Analysis: ask the LLM for a strategy
        fsm = fsm.transition(Phase.ANALYSIS)
        strategy_resp = await self._llm_determine_strategy(provider, model, user_input)
        strategy = strategy_resp.content
        analysis_data: dict[str, Any] = {"strategy": strategy}
        evidence.add("analysis", "decision", analysis_data)
        results.append(PhaseResult(phase="analysis", data=analysis_data, confidence=0.9))

        # Phase 3 — Planning: ask the LLM for an execution plan
        fsm = fsm.transition(Phase.PLANNING)
        plan_resp = await self._llm_create_plan(provider, model, user_input, strategy)
        plan_text = plan_resp.content
        plan: dict[str, Any] = {"strategy": strategy, "llm_plan": plan_text}
        plan_data: dict[str, Any] = {"plan": plan}
        evidence.add("planning", "decision", plan_data)
        results.append(PhaseResult(phase="planning", data=plan_data, confidence=0.85))

        # Phase 4 — Execution: ask the LLM to execute
        fsm = fsm.transition(Phase.EXECUTION)
        exec_resp = await self._llm_execute(provider, model, user_input, plan_text)
        exec_output = exec_resp.content
        exec_data: dict[str, Any] = {"output": exec_output}
        evidence.add("execution", "output", exec_data)
        results.append(PhaseResult(phase="execution", data=exec_data, confidence=0.8))

        # Phase 5 — Validation (deterministic)
        fsm = fsm.transition(Phase.VALIDATION)
        valid = self._validate(exec_output)
        val_data: dict[str, Any] = {"passed": valid, "output": exec_output}
        evidence.add("validation", "decision", val_data)
        val_confidence = 0.9 if valid else 0.4
        results.append(
            PhaseResult(phase="validation", data=val_data, confidence=val_confidence)
        )

        # Phase 6 — Synthesis: ask the LLM for a final answer
        fsm = fsm.transition(Phase.SYNTHESIS)
        synth_resp = await self._llm_synthesize(provider, model, user_input, exec_output)
        final = synth_resp.content
        synth_data: dict[str, Any] = {"final": final}
        evidence.add("synthesis", "output", synth_data)
        results.append(PhaseResult(phase="synthesis", data=synth_data, confidence=0.95))

        # Phase 7 — Complete
        fsm = fsm.transition(Phase.COMPLETE)
        complete_data: dict[str, Any] = {"status": "complete", "phases_run": len(results)}
        evidence.add("complete", "output", complete_data)
        results.append(PhaseResult(phase="complete", data=complete_data, confidence=1.0))

        return results

    # ------------------------------------------------------------------
    # LLM helper methods (used by run_with_provider)
    # ------------------------------------------------------------------

    @staticmethod
    async def _llm_determine_strategy(
        provider: LLMProvider, model: str, user_input: str
    ) -> ChatResponse:
        from .provider import ChatMessage, ChatRequest, ChatRole

        return await provider.chat(
            ChatRequest(
                model=model,
                messages=[
                    ChatMessage(
                        role=ChatRole.SYSTEM,
                        content="Determine the best processing strategy for this input. "
                        "Reply with a single strategy name.",
                    ),
                    ChatMessage(role=ChatRole.USER, content=user_input),
                ],
            )
        )

    @staticmethod
    async def _llm_create_plan(
        provider: LLMProvider, model: str, user_input: str, strategy: str
    ) -> ChatResponse:
        from .provider import ChatMessage, ChatRequest, ChatRole

        return await provider.chat(
            ChatRequest(
                model=model,
                messages=[
                    ChatMessage(
                        role=ChatRole.SYSTEM,
                        content=f"Create an execution plan using the '{strategy}' strategy.",
                    ),
                    ChatMessage(role=ChatRole.USER, content=user_input),
                ],
            )
        )

    @staticmethod
    async def _llm_execute(
        provider: LLMProvider, model: str, user_input: str, plan: str
    ) -> ChatResponse:
        from .provider import ChatMessage, ChatRequest, ChatRole

        return await provider.chat(
            ChatRequest(
                model=model,
                messages=[
                    ChatMessage(
                        role=ChatRole.SYSTEM,
                        content=f"Execute this plan and produce the result.\n\nPlan:\n{plan}",
                    ),
                    ChatMessage(role=ChatRole.USER, content=user_input),
                ],
            )
        )

    @staticmethod
    async def _llm_synthesize(
        provider: LLMProvider, model: str, user_input: str, exec_output: str
    ) -> ChatResponse:
        from .provider import ChatMessage, ChatRequest, ChatRole

        return await provider.chat(
            ChatRequest(
                model=model,
                messages=[
                    ChatMessage(
                        role=ChatRole.SYSTEM,
                        content="Synthesize the execution output into a final answer.",
                    ),
                    ChatMessage(
                        role=ChatRole.USER,
                        content=(
                            f"Original request: {user_input}\n\n"
                            f"Execution output:\n{exec_output}"
                        ),
                    ),
                ],
            )
        )

"""RefinementHarness -- the main generate-verify-refine loop."""

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
    """Orchestrates the generate-verify-refine loop.

    Composes a :class:`CandidateGenerator`, :class:`Verifier`,
    :class:`RefinementPolicy`, and :class:`Selector` to iteratively
    produce, evaluate, and refine LLM outputs until a quality threshold
    is met or the round budget is exhausted.

    Each step is traced to an optional :class:`EvidencePack` for
    auditable execution (EU AI Act Art. 12).
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

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self, task: str, config: HarnessConfig) -> HarnessResult:
        """Execute the generate-verify-refine loop.

        Parameters
        ----------
        task:
            The user's request or problem statement.
        config:
            Harness configuration (providers, rounds, score threshold).

        Returns
        -------
        HarnessResult:
            The winning candidate, its feedback, round count, and
            total candidate count.
        """
        # Step 1 -- optionally recall patterns from memory store
        context = ""
        if self._memory:
            patterns = self._memory.recall_patterns(task)
            if patterns:
                context = f"Previous patterns: {patterns[0]}"

        if self._evidence:
            self._evidence.add(
                phase="harness",
                kind="input",
                data={"task": task, "has_memory_context": bool(context)},
            )

        all_candidates: list[tuple[Candidate, Feedback]] = []
        best_score = 0.0
        current_task = task
        round_num = 0

        # Step 2 -- loop: generate -> verify -> track best -> check policy
        while self._policy.should_continue(
            round_num, best_score, [f for _, f in all_candidates]
        ):
            candidates = await self._generator.generate(current_task, context, config)

            for candidate in candidates:
                feedback = self._verifier.verify(candidate, task)
                all_candidates.append((candidate, feedback))

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

            # Step 3 -- if policy says continue, refine using worst feedback
            if self._policy.should_continue(
                round_num, best_score, [f for _, f in all_candidates]
            ):
                worst = min(all_candidates, key=lambda x: x[1].score)
                current_task = self._policy.refine_prompt(task, worst[1])

        # Step 4 -- select winner via selector (score + consensus)
        winner = self._selector.select(all_candidates)
        winner_feedback = next(f for c, f in all_candidates if c.id == winner.id)

        # Step 5 -- store winning pattern in memory
        if self._memory:
            self._memory.store_pattern(task, winner, winner_feedback)

        # Step 6 -- trace selection decision to evidence
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

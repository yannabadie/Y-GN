"""Context builder — assembles execution context from services."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from .evidence import EvidencePack
from .guard import GuardPipeline, GuardResult
from .memory import MemoryEntry, MemoryService


@dataclass
class ExecutionContext:
    """Full execution context for a pipeline run."""

    user_input: str
    session_id: str
    memories: list[MemoryEntry]
    guard_result: GuardResult
    plan: dict[str, object] | None
    evidence: EvidencePack


class ContextBuilder:
    """Assembles an ExecutionContext from user input and services."""

    def build(
        self,
        user_input: str,
        session_id: str | None = None,
        memory_service: MemoryService | None = None,
        guard_pipeline: GuardPipeline | None = None,
    ) -> ExecutionContext:
        """Build a complete execution context.

        1. Generate session ID if not provided.
        2. Retrieve relevant memories via memory service.
        3. Validate input through guard pipeline.
        4. Create a fresh evidence pack.
        """
        sid = session_id if session_id is not None else uuid.uuid4().hex[:12]

        # Retrieve memories
        memories: list[MemoryEntry] = []
        if memory_service is not None:
            memories = memory_service.recall(user_input, limit=5)

        # Guard evaluation
        guard = guard_pipeline if guard_pipeline is not None else GuardPipeline()
        guard_result = guard.evaluate(user_input)

        # Evidence pack
        evidence = EvidencePack(session_id=sid)
        evidence.add("context", "input", {"user_input": user_input})
        if memories:
            evidence.add(
                "context",
                "decision",
                {"memories_retrieved": len(memories)},
            )
        evidence.add(
            "context",
            "decision",
            {
                "guard_allowed": guard_result.allowed,
                "threat_level": guard_result.threat_level,
            },
        )

        return ExecutionContext(
            user_input=user_input,
            session_id=sid,
            memories=memories,
            guard_result=guard_result,
            plan=None,
            evidence=evidence,
        )

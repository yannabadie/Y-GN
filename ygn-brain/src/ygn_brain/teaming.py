"""Dynamic Teaming + Flow Control — team formation, flow policies, and distributed swarm."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .swarm import SwarmMode, SwarmResult, TaskAnalysis, TaskAnalyzer, TaskComplexity

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class AgentProfile:
    """Describes a single agent in the distributed grid."""

    agent_id: str
    node_id: str
    role: str  # "planner", "executor", "validator", "specialist"
    capabilities: list[str]
    trust_level: float  # 0.0 to 1.0
    is_local: bool


@dataclass
class TeamFormation:
    """A formed team of agents ready to execute a task."""

    team_id: str
    agents: list[AgentProfile]
    lead_agent_id: str
    strategy: str  # SwarmMode name to use
    created_at: float


# ---------------------------------------------------------------------------
# Flow control
# ---------------------------------------------------------------------------


class FlowPolicy(StrEnum):
    ROUND_ROBIN = "round_robin"
    LEAD_FIRST = "lead_first"
    CAPABILITY_MATCH = "capability_match"
    DEBATE = "debate"


class FlowController:
    """Controls conversation flow among agents based on a chosen policy."""

    def __init__(self, policy: FlowPolicy, agents: list[AgentProfile]) -> None:
        self._policy = policy
        self._agents = list(agents)
        self._turn_index: int = 0

    def next_speaker(self, conversation: list[dict[str, Any]]) -> AgentProfile:
        """Pick the next agent to speak based on the active flow policy."""
        if self._policy == FlowPolicy.ROUND_ROBIN:
            return self._round_robin(conversation)
        if self._policy == FlowPolicy.LEAD_FIRST:
            return self._lead_first(conversation)
        if self._policy == FlowPolicy.CAPABILITY_MATCH:
            return self._capability_match(conversation)
        # DEBATE
        return self._debate(conversation)

    def should_conclude(self, conversation: list[dict[str, Any]], max_rounds: int = 5) -> bool:
        """Decide when to stop the discussion."""
        if not self._agents:
            return True
        rounds = len(conversation) // max(len(self._agents), 1)
        return rounds >= max_rounds

    # -- Private strategies --------------------------------------------------

    def _round_robin(self, conversation: list[dict[str, Any]]) -> AgentProfile:
        """Cycle through agents in order."""
        idx = len(conversation) % len(self._agents)
        return self._agents[idx]

    def _lead_first(self, conversation: list[dict[str, Any]]) -> AgentProfile:
        """Lead speaks first, then others respond in trust-level order."""
        if not conversation:
            # First turn: pick the agent with the highest trust level (the lead)
            return max(self._agents, key=lambda a: a.trust_level)

        # Subsequent turns: cycle through others sorted by trust level descending
        non_lead = sorted(
            self._agents,
            key=lambda a: a.trust_level,
            reverse=True,
        )
        idx = (len(conversation) - 1) % len(non_lead)
        return non_lead[idx]

    def _capability_match(self, conversation: list[dict[str, Any]]) -> AgentProfile:
        """Next speaker is the one whose capabilities best match unresolved aspects."""
        # Collect words from conversation that hint at unresolved topics
        unresolved_words: set[str] = set()
        for turn in conversation:
            content: str = turn.get("content", "")
            unresolved_words.update(content.lower().split())

        def _score(agent: AgentProfile) -> int:
            return sum(1 for cap in agent.capabilities if cap.lower() in unresolved_words)

        scored = sorted(self._agents, key=_score, reverse=True)
        return scored[0]

    def _debate(self, conversation: list[dict[str, Any]]) -> AgentProfile:
        """Alternate between agents with different roles."""
        if not conversation:
            return self._agents[0]

        last_role = ""
        last_speaker_id = conversation[-1].get("agent_id", "")
        for agent in self._agents:
            if agent.agent_id == last_speaker_id:
                last_role = agent.role
                break

        # Pick an agent with a different role
        for agent in self._agents:
            if agent.role != last_role:
                return agent

        # Fallback: round-robin
        return self._round_robin(conversation)


# ---------------------------------------------------------------------------
# Team builder
# ---------------------------------------------------------------------------


class TeamBuilder:
    """Forms and dissolves teams from a pool of available agents."""

    def __init__(self, available_agents: list[AgentProfile]) -> None:
        self._available_agents = list(available_agents)
        self._active_teams: dict[str, TeamFormation] = {}

    def form_team(self, task_analysis: TaskAnalysis, max_size: int = 4) -> TeamFormation:
        """Select agents, assign a lead, and choose a strategy."""
        # Score agents by how many of their capabilities match the task domains
        scored: list[tuple[AgentProfile, int]] = []
        for agent in self._available_agents:
            score = sum(1 for cap in agent.capabilities if cap in task_analysis.domains)
            scored.append((agent, score))

        # Sort by score descending, then by trust level descending
        scored.sort(key=lambda pair: (pair[1], pair[0].trust_level), reverse=True)

        selected = [agent for agent, _ in scored[:max_size]]

        # If we got nothing (unlikely), take first available agents
        if not selected:
            selected = self._available_agents[:max_size]

        # Lead is the agent with the highest trust level
        lead = max(selected, key=lambda a: a.trust_level)

        # Strategy based on complexity
        strategy = self._pick_strategy(task_analysis.complexity).value

        team = TeamFormation(
            team_id=uuid.uuid4().hex[:12],
            agents=selected,
            lead_agent_id=lead.agent_id,
            strategy=strategy,
            created_at=time.time(),
        )
        self._active_teams[team.team_id] = team
        return team

    def dissolve_team(self, team_id: str) -> None:
        """Remove a team from the active roster."""
        self._active_teams.pop(team_id, None)

    @property
    def active_teams(self) -> dict[str, TeamFormation]:
        """Return a read-only view of active teams."""
        return dict(self._active_teams)

    @staticmethod
    def _pick_strategy(complexity: TaskComplexity) -> SwarmMode:
        """Map task complexity to a SwarmMode strategy."""
        if complexity in (TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE):
            return SwarmMode.SEQUENTIAL
        if complexity == TaskComplexity.MODERATE:
            return SwarmMode.LEAD_SUPPORT
        if complexity == TaskComplexity.COMPLEX:
            return SwarmMode.PARALLEL
        # EXPERT
        return SwarmMode.SPECIALIST


# ---------------------------------------------------------------------------
# Distributed swarm engine
# ---------------------------------------------------------------------------


class DistributedSwarmEngine:
    """Extends the SwarmEngine concept with team formation and flow control."""

    def __init__(
        self,
        team_builder: TeamBuilder,
        flow_controller_factory: Callable[[FlowPolicy, list[AgentProfile]], FlowController],
    ) -> None:
        self._team_builder = team_builder
        self._flow_controller_factory = flow_controller_factory
        self._analyzer = TaskAnalyzer()

    def run_distributed(self, user_input: str, available_agents: list[AgentProfile]) -> SwarmResult:
        """Analyze task, form team, simulate multi-agent conversation, return result."""
        # 1. Analyze the task
        analysis = self._analyzer.analyze(user_input)

        # 2. Form a team
        self._team_builder._available_agents = list(available_agents)  # noqa: SLF001
        team = self._team_builder.form_team(analysis)

        # 3. Choose flow policy based on strategy
        policy = self._strategy_to_policy(team.strategy)

        # 4. Create flow controller
        controller = self._flow_controller_factory(policy, team.agents)

        # 5. Simulate multi-agent conversation
        conversation: list[dict[str, Any]] = []
        max_rounds = 5
        while not controller.should_conclude(conversation, max_rounds):
            speaker = controller.next_speaker(conversation)
            turn: dict[str, Any] = {
                "agent_id": speaker.agent_id,
                "role": speaker.role,
                "content": f"[{speaker.role}] Response to: {user_input}",
            }
            conversation.append(turn)

        # 6. Aggregate and return result
        output_parts = [turn["content"] for turn in conversation]
        return SwarmResult(
            mode=self._resolve_mode(team.strategy),
            output="\n".join(output_parts) if output_parts else f"Processed: {user_input}",
            metadata={
                "team_id": team.team_id,
                "lead_agent_id": team.lead_agent_id,
                "agents": [a.agent_id for a in team.agents],
                "conversation_turns": len(conversation),
                "strategy": team.strategy,
            },
        )

    @staticmethod
    def _resolve_mode(strategy: str) -> SwarmMode:
        """Safely convert a strategy string to a SwarmMode."""
        try:
            return SwarmMode(strategy)
        except ValueError:
            return SwarmMode.SEQUENTIAL

    @staticmethod
    def _strategy_to_policy(strategy: str) -> FlowPolicy:
        """Map a SwarmMode strategy name to a FlowPolicy."""
        mapping: dict[str, FlowPolicy] = {
            SwarmMode.PARALLEL.value: FlowPolicy.ROUND_ROBIN,
            SwarmMode.SEQUENTIAL.value: FlowPolicy.ROUND_ROBIN,
            SwarmMode.RED_BLUE.value: FlowPolicy.DEBATE,
            SwarmMode.PING_PONG.value: FlowPolicy.DEBATE,
            SwarmMode.LEAD_SUPPORT.value: FlowPolicy.LEAD_FIRST,
            SwarmMode.SPECIALIST.value: FlowPolicy.CAPABILITY_MATCH,
        }
        return mapping.get(strategy, FlowPolicy.ROUND_ROBIN)

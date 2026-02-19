"""Tests for teaming module — dynamic teaming and flow control."""

from __future__ import annotations

from ygn_brain.swarm import SwarmMode, TaskAnalysis, TaskComplexity
from ygn_brain.teaming import (
    AgentProfile,
    DistributedSwarmEngine,
    FlowController,
    FlowPolicy,
    TeamBuilder,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agents() -> list[AgentProfile]:
    """Build a pool of test agents with varied capabilities."""
    return [
        AgentProfile(
            agent_id="agent-planner",
            node_id="node-1",
            role="planner",
            capabilities=["research", "writing"],
            trust_level=0.9,
            is_local=True,
        ),
        AgentProfile(
            agent_id="agent-executor",
            node_id="node-2",
            role="executor",
            capabilities=["code", "data"],
            trust_level=0.8,
            is_local=False,
        ),
        AgentProfile(
            agent_id="agent-validator",
            node_id="node-3",
            role="validator",
            capabilities=["research", "math"],
            trust_level=0.7,
            is_local=False,
        ),
        AgentProfile(
            agent_id="agent-specialist",
            node_id="node-4",
            role="specialist",
            capabilities=["design", "code"],
            trust_level=0.6,
            is_local=True,
        ),
    ]


def _task_analysis(
    complexity: TaskComplexity = TaskComplexity.MODERATE,
    domains: list[str] | None = None,
) -> TaskAnalysis:
    return TaskAnalysis(
        complexity=complexity,
        domains=domains if domains is not None else ["code", "research"],
        suggested_mode=SwarmMode.LEAD_SUPPORT,
    )


# ---------------------------------------------------------------------------
# TeamBuilder tests
# ---------------------------------------------------------------------------


def test_team_builder_forms_team() -> None:
    """TeamBuilder.form_team returns a TeamFormation with agents."""
    builder = TeamBuilder(_make_agents())
    team = builder.form_team(_task_analysis())
    assert len(team.agents) > 0
    assert team.team_id


def test_team_builder_assigns_lead_by_trust() -> None:
    """Lead agent should be the one with the highest trust level in the team."""
    builder = TeamBuilder(_make_agents())
    team = builder.form_team(_task_analysis())
    lead = max(team.agents, key=lambda a: a.trust_level)
    assert team.lead_agent_id == lead.agent_id


def test_team_builder_matches_capabilities_to_domains() -> None:
    """Agents whose capabilities overlap the task domains are preferred."""
    agents = _make_agents()
    builder = TeamBuilder(agents)
    analysis = _task_analysis(domains=["code"])
    team = builder.form_team(analysis, max_size=2)
    # The two agents with "code" capability should be selected
    ids = {a.agent_id for a in team.agents}
    assert "agent-executor" in ids
    assert "agent-specialist" in ids


def test_team_builder_limits_team_size() -> None:
    """Max size parameter caps the number of agents on the team."""
    builder = TeamBuilder(_make_agents())
    team = builder.form_team(_task_analysis(), max_size=2)
    assert len(team.agents) <= 2


# ---------------------------------------------------------------------------
# FlowController tests
# ---------------------------------------------------------------------------


def test_flow_controller_round_robin() -> None:
    """Round-robin policy cycles through agents in order."""
    agents = _make_agents()[:3]
    ctrl = FlowController(FlowPolicy.ROUND_ROBIN, agents)
    conversation: list[dict[str, object]] = []
    speakers = []
    for _ in range(6):
        speaker = ctrl.next_speaker(conversation)  # type: ignore[arg-type]
        speakers.append(speaker.agent_id)
        conversation.append({"agent_id": speaker.agent_id, "content": "turn"})

    # Should cycle: 0, 1, 2, 0, 1, 2
    assert speakers == [
        agents[0].agent_id,
        agents[1].agent_id,
        agents[2].agent_id,
        agents[0].agent_id,
        agents[1].agent_id,
        agents[2].agent_id,
    ]


def test_flow_controller_lead_first() -> None:
    """Lead-first policy picks the highest-trust agent first."""
    agents = _make_agents()[:3]
    ctrl = FlowController(FlowPolicy.LEAD_FIRST, agents)
    first = ctrl.next_speaker([])
    assert first.agent_id == max(agents, key=lambda a: a.trust_level).agent_id


def test_flow_controller_capability_match() -> None:
    """Capability-match picks the agent whose capabilities appear in conversation."""
    agents = _make_agents()
    ctrl = FlowController(FlowPolicy.CAPABILITY_MATCH, agents)
    conversation: list[dict[str, object]] = [
        {"agent_id": "x", "content": "We need to work on code and design"},
    ]
    speaker = ctrl.next_speaker(conversation)  # type: ignore[arg-type]
    # agent-specialist has ["design", "code"] — both match
    assert speaker.agent_id == "agent-specialist"


def test_flow_controller_should_conclude_after_max_rounds() -> None:
    """should_conclude returns True when enough rounds have elapsed."""
    agents = _make_agents()[:2]
    ctrl = FlowController(FlowPolicy.ROUND_ROBIN, agents)
    # 2 agents * 5 rounds = 10 turns needed
    conversation: list[dict[str, object]] = [{"agent_id": "a", "content": "x"} for _ in range(10)]
    assert ctrl.should_conclude(conversation, max_rounds=5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# DistributedSwarmEngine end-to-end
# ---------------------------------------------------------------------------


def test_distributed_swarm_engine_end_to_end() -> None:
    """DistributedSwarmEngine runs analysis, team formation, and conversation."""
    agents = _make_agents()
    builder = TeamBuilder(agents)
    engine = DistributedSwarmEngine(
        team_builder=builder,
        flow_controller_factory=FlowController,
    )
    result = engine.run_distributed("Write code and research the topic", agents)
    assert result.output
    assert result.metadata["conversation_turns"] > 0
    assert result.metadata["team_id"]


# ---------------------------------------------------------------------------
# Team dissolve
# ---------------------------------------------------------------------------


def test_team_dissolve_removes_team() -> None:
    """After dissolve_team, the team should be gone from active_teams."""
    builder = TeamBuilder(_make_agents())
    team = builder.form_team(_task_analysis())
    assert team.team_id in builder.active_teams
    builder.dissolve_team(team.team_id)
    assert team.team_id not in builder.active_teams

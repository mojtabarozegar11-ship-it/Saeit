import pytest
from django.contrib.auth import get_user_model
from core.agent_registry import AgentRegistry
from core.models import Agent, AgentCapability, ResearchProject
from core.orchestrator import MasterAgent
from core.task_runtime import TaskExecutionError, TaskRuntime

pytestmark = pytest.mark.django_db


def setup_capability(risk="low"):
    user = get_user_model().objects.create_user(username="policy-owner")
    project = ResearchProject.objects.create(title="Policy", objective="Test", owner=user)
    agent = Agent.objects.create(code="policy-agent", name="Policy Agent", mission="", active=True)
    capability = AgentCapability.objects.create(code="collect_source", name="Collect", risk_level=risk)
    capability.agents.add(agent)
    return project, agent, capability


def test_capability_risk_can_force_owner_approval():
    project, _, _ = setup_capability("high")
    task = MasterAgent().plan(project, "collect_source", {})
    assert task.status == "blocked"


def test_low_risk_capability_remains_queued():
    project, _, _ = setup_capability("low")
    task = MasterAgent().plan(project, "collect_source", {})
    assert task.status == "queued"


def test_task_persists_normalized_action_for_runtime_policy():
    project, _, _ = setup_capability("low")
    task = MasterAgent().plan(project, "collect-source", {})
    assert task.action_type == "collect_source"


def test_registry_effective_risk_never_downgrades_capability_risk():
    _, _, capability = setup_capability("critical")
    assert AgentRegistry().effective_risk(capability, "low") == "critical"
    assert AgentRegistry().effective_risk(capability, "high") == "critical"


def test_blocked_task_remains_unclaimable_even_with_active_agent():
    project, agent, _ = setup_capability("high")
    task = MasterAgent().plan(project, "collect_source", {})
    assert task.agent_id == agent.id
    with pytest.raises(TaskExecutionError):
        TaskRuntime().claim(task.pk)

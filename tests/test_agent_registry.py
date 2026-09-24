import pytest
from django.contrib.auth import get_user_model
from core.agent_registry import AgentRegistry
from core.models import Agent, AgentCapability, ResearchProject
from core.orchestrator import MasterAgent

pytestmark = pytest.mark.django_db


def test_registry_resolves_exact_capability():
    user = get_user_model().objects.create_user(username="registry-owner")
    ResearchProject.objects.create(title="P", objective="O", owner=user)
    agent = Agent.objects.create(code="researcher", name="Researcher", mission="research", active=True)
    capability = AgentCapability.objects.create(code="collect_source", name="Collect source")
    capability.agents.add(agent)
    assert AgentRegistry().resolve("collect_source") == agent


def test_registry_rejects_inactive_capability():
    user = get_user_model().objects.create_user(username="registry-owner-2")
    ResearchProject.objects.create(title="P2", objective="O", owner=user)
    agent = Agent.objects.create(code="researcher-2", name="Researcher", mission="research", active=True)
    capability = AgentCapability.objects.create(code="publish", name="Publish", active=False)
    capability.agents.add(agent)
    assert AgentRegistry().resolve("publish") is None


def test_master_agent_uses_capability_registry_before_mission_fallback():
    user = get_user_model().objects.create_user(username="registry-owner-3")
    project = ResearchProject.objects.create(title="P3", objective="O", owner=user)
    generic = Agent.objects.create(code="generic", name="Generic", mission="publish", active=True)
    specialist = Agent.objects.create(code="specialist", name="Specialist", mission="research", active=True)
    capability = AgentCapability.objects.create(code="publish", name="Publish")
    capability.agents.add(specialist)
    task = MasterAgent().plan(project, "publish", {})
    assert task.agent_id == specialist.id

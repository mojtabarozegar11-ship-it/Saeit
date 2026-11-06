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


def test_registry_does_not_route_compound_action_to_unrelated_token_capability():
    agent = Agent.objects.create(code="news-token-agent", name="News", mission="news", active=True)
    capability = AgentCapability.objects.create(code="news", name="News")
    capability.agents.add(agent)

    assert AgentRegistry().resolve("news_publish") is None


def test_master_agent_rejects_mission_only_match_before_enqueuing():
    user = get_user_model().objects.create_user(username="mission-only-owner")
    project = ResearchProject.objects.create(title="Mission only", objective="No phantom task", owner=user)
    Agent.objects.create(
        code="mission-only-agent", name="Mission", mission="news_publish", active=True
    )

    with pytest.raises(RuntimeError, match="No active agent"):
        MasterAgent().plan(project, "news_publish", {})


def test_registry_supports_core_prefixed_capability_accepted_by_runtime():
    agent = Agent.objects.create(code="research-core-agent", name="Core", mission="research", active=True)
    capability = AgentCapability.objects.create(code="core_collect_source", name="Collect")
    capability.agents.add(agent)

    assert AgentRegistry().resolve("collect_source") == agent
    assert AgentRegistry().capability_for(agent, "collect_source") == capability


def test_registry_prefers_low_risk_agent_before_critical_risk_agent():
    critical = Agent.objects.create(
        code="critical-agent", name="Critical", mission="publish", risk_level="critical", active=True
    )
    low = Agent.objects.create(
        code="low-agent", name="Low", mission="publish", risk_level="low", active=True
    )
    capability = AgentCapability.objects.create(code="publish", name="Publish")
    capability.agents.add(critical, low)

    assert AgentRegistry().resolve("publish") == low

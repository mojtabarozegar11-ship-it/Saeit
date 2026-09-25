import pytest

from core.models import Agent, AgentCapability


@pytest.mark.django_db
def test_core_research_agent_is_seeded():
    agent = Agent.objects.get(code="core_research")
    capability = AgentCapability.objects.get(code="research")

    assert agent.active is True
    assert capability.active is True
    assert agent.capabilities.filter(pk=capability.pk).exists()

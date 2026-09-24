import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Agent, AgentCapability, ApprovalRequest, ResearchProject


def setup_runtime():
    user = get_user_model().objects.create_user(username="owner", password="pass", is_staff=True)
    project = ResearchProject.objects.create(title="Runtime test", objective="Controlled planning", owner=user)
    agent = Agent.objects.create(code="research_agent", name="Research Agent", mission="research", active=True)
    capability = AgentCapability.objects.create(code="research", name="Research", risk_level="low", active=True)
    capability.agents.add(agent)
    return user, project, agent, capability


@pytest.mark.django_db
def test_master_agent_plan_queues_low_risk_task():
    user, project, agent, capability = setup_runtime()
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/master-chat/plan/",
        {"project_id": project.pk, "action_type": "research", "payload": {"topic": "agriculture"}, "risk": "low"},
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["agent"] == agent.pk
    assert body["capability_code"] == capability.code
    assert ApprovalRequest.objects.count() == 0

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Agent, AgentCapability, ResearchProject


@pytest.mark.django_db
def test_plan_api_rejects_invalid_risk():
    user = get_user_model().objects.create_user(username="risk-api", password="pass", is_staff=True)
    project = ResearchProject.objects.create(title="Risk API", objective="Validation", owner=user)
    agent = Agent.objects.create(code="research_risk", name="Research", mission="research", active=True)
    capability = AgentCapability.objects.create(code="research_risk", name="Research", active=True)
    capability.agents.add(agent)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/master-chat/plan/",
        {
            "project_id": project.pk,
            "action_type": "research_risk",
            "risk": "unknown",
        },
        format="json",
    )

    assert response.status_code == 409
    assert "Invalid risk level" in response.json()["detail"]

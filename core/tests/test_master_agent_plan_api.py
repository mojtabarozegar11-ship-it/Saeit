import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Agent, AgentCapability, ApprovalRequest, ResearchProject


@pytest.mark.django_db
def test_master_agent_plan_requires_owner_approval_for_sensitive_action():
    user = get_user_model().objects.create_user(username="owner", password="pass", is_staff=True)
    project = ResearchProject.objects.create(
        title="Runtime test",
        objective="Controlled planning",
        owner=user,
    )
    agent = Agent.objects.create(
        code="deployment_agent",
        name="Deployment Agent",
        mission="deployment",
        risk_level="high",
        active=True,
    )
    capability = AgentCapability.objects.create(
        code="deploy",
        name="Deploy",
        risk_level="high",
        active=True,
    )
    capability.agents.add(agent)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/master-chat/plan/",
        {
            "project_id": project.pk,
            "action_type": "deploy",
            "payload": {"target": "production"},
            "risk": "high",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "blocked"
    approval = ApprovalRequest.objects.get(target_type="AgentTask", target_id=str(response.json()["id"]))
    assert approval.status == "pending"


@pytest.mark.django_db
def test_master_agent_plan_rejects_unknown_capability():
    user = get_user_model().objects.create_user(username="owner2", password="pass", is_staff=True)
    project = ResearchProject.objects.create(
        title="Runtime test",
        objective="Controlled planning",
        owner=user,
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/master-chat/plan/",
        {
            "project_id": project.pk,
            "action_type": "unknown_action",
        },
        format="json",
    )

    assert response.status_code == 409

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Agent, AgentCapability, ApprovalRequest, AgentTask, ResearchProject


@pytest.mark.django_db
def test_approval_api_releases_task_for_designated_owner():
    User = get_user_model()
    owner = User.objects.create_user(username="api-owner", password="pass", is_staff=True)
    project = ResearchProject.objects.create(title="Approval API", objective="Controlled release", owner=owner)
    agent = Agent.objects.create(code="deploy_api", name="Deploy", mission="deploy", active=True)
    capability = AgentCapability.objects.create(code="deploy_api", name="Deploy", risk_level="high", active=True)
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        action_type="deploy_api",
        capability_code="deploy_api",
        risk_snapshot="high",
        status="blocked",
    )
    approval = ApprovalRequest.objects.create(
        action_type="deploy_api",
        target_type="AgentTask",
        target_id=str(task.pk),
        reason="Owner approval required",
        risk="high",
        requested_by=owner,
    )

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f"/api/approvals/{approval.pk}/decide/",
        {"approved": True, "note": "Approved by owner"},
        format="json",
    )

    assert response.status_code == 200
    task.refresh_from_db()
    assert task.status == "queued"


@pytest.mark.django_db
def test_approval_api_rejects_non_owner():
    User = get_user_model()
    owner = User.objects.create_user(username="api-owner-2", password="pass", is_staff=True)
    other = User.objects.create_user(username="api-other", password="pass", is_staff=True)
    project = ResearchProject.objects.create(title="Approval API", objective="Ownership", owner=owner)
    agent = Agent.objects.create(code="secure_api", name="Secure", mission="secure", active=True)
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        action_type="secure_api",
        capability_code="secure_api",
        risk_snapshot="high",
        status="blocked",
    )
    approval = ApprovalRequest.objects.create(
        action_type="secure_api",
        target_type="AgentTask",
        target_id=str(task.pk),
        reason="Owner approval required",
        risk="high",
        requested_by=owner,
    )

    client = APIClient()
    client.force_authenticate(user=other)
    response = client.post(
        f"/api/approvals/{approval.pk}/decide/",
        {"approved": True},
        format="json",
    )

    assert response.status_code == 403
    approval.refresh_from_db()
    task.refresh_from_db()
    assert approval.status == "pending"
    assert task.status == "blocked"

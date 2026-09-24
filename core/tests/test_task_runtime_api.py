import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_claim_missing_task_returns_404():
    user = get_user_model().objects.create_user(
        username="runtime-missing", password="pass", is_staff=True
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post("/api/tasks/999999/claim/", {}, format="json")

    assert response.status_code == 404
    assert response.data["detail"] == "Task not found."


@pytest.mark.django_db
def test_heartbeat_endpoint():
    from core.models import Agent, AgentCapability, AgentTask, ResearchProject

    user = get_user_model().objects.create_user(
        username="runtime-heartbeat", password="pass", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Runtime API", objective="Heartbeat", owner=user
    )
    agent = Agent.objects.create(
        code="heartbeat-agent", name="Heartbeat", mission="Heartbeat test", active=True
    )
    capability = AgentCapability.objects.create(
        code="heartbeat", name="Heartbeat", active=True
    )
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, project=project, action_type="heartbeat",
        capability_code="heartbeat", risk_snapshot="low",
        status="running", execution_id="api-exec-1", attempt_count=1
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        f"/api/tasks/{task.pk}/heartbeat/",
        {"execution_id": "api-exec-1"}, format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "running"


@pytest.mark.django_db
def test_recover_stale_endpoint():
    from datetime import timedelta
    from django.utils import timezone
    from core.models import Agent, AgentCapability, AgentTask, ResearchProject

    user = get_user_model().objects.create_user(
        username="runtime-recover", password="pass", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Runtime API", objective="Recovery", owner=user
    )
    agent = Agent.objects.create(
        code="recover-agent", name="Recovery", mission="Recovery test", active=True
    )
    capability = AgentCapability.objects.create(
        code="recover", name="Recovery", active=True
    )
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, project=project, action_type="recover",
        capability_code="recover", risk_snapshot="low",
        status="running", execution_id="api-recover-1", attempt_count=1
    )
    AgentTask.objects.filter(pk=task.pk).update(
        updated_at=timezone.now() - timedelta(minutes=30)
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        f"/api/tasks/{task.pk}/recover-stale/",
        {"stale_after_seconds": 60}, format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "queued"
    assert response.data["execution_id"] == ""

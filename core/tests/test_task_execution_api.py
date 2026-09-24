import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Agent, AgentCapability, AgentTask, ResearchProject


def make_running_task(owner):
    project = ResearchProject.objects.create(
        title="API Runtime", objective="Execution", owner=owner
    )
    agent = Agent.objects.create(
        code="api_runtime_agent", name="Runtime", mission="runtime", active=True
    )
    capability = AgentCapability.objects.create(
        code="runtime", name="Runtime", active=True
    )
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        action_type="runtime",
        capability_code="runtime",
        risk_snapshot="low",
        status="running",
        execution_id="execution-test",
        attempt_count=1,
    )
    return task


@pytest.mark.django_db
def test_complete_endpoint_finishes_running_task():
    user = get_user_model().objects.create_user(
        username="complete-api", password="pass", is_staff=True
    )
    task = make_running_task(user)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        f"/api/tasks/{task.pk}/complete/",
        {"output_data": {"ok": True}, "cost": "1.25", "execution_id": task.execution_id},
        format="json",
    )

    assert response.status_code == 200
    task.refresh_from_db()
    assert task.status == "completed"
    assert task.output_data == {"ok": True}


@pytest.mark.django_db
def test_fail_endpoint_requeues_running_task():
    user = get_user_model().objects.create_user(
        username="fail-api", password="pass", is_staff=True
    )
    task = make_running_task(user)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        f"/api/tasks/{task.pk}/fail/",
        {"error": "temporary", "execution_id": task.execution_id},
        format="json",
    )

    assert response.status_code == 200
    task.refresh_from_db()
    assert task.status == "queued"


@pytest.mark.django_db
def test_execution_endpoints_require_staff():
    user = get_user_model().objects.create_user(
        username="nonstaff-execution", password="pass"
    )
    task = make_running_task(user)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        f"/api/tasks/{task.pk}/complete/",
        {"output_data": {"ok": True}},
        format="json",
    )

    assert response.status_code == 403

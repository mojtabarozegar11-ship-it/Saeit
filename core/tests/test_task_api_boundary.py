import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Agent, AgentCapability, ResearchProject


@pytest.mark.django_db
def test_direct_agent_task_creation_is_blocked():
    user = get_user_model().objects.create_user(username="task-writer", password="pass", is_staff=True)
    project = ResearchProject.objects.create(title="Runtime", objective="Boundary", owner=user)
    agent = Agent.objects.create(code="research", name="Research", mission="research", active=True)
    capability = AgentCapability.objects.create(code="research", name="Research", active=True)
    capability.agents.add(agent)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/tasks/",
        {
            "agent": agent.pk,
            "project": project.pk,
            "action_type": "research",
            "capability_code": "research",
            "risk_snapshot": "low",
        },
        format="json",
    )

    assert response.status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_agent_task_mutations_are_blocked(method):
    user = get_user_model().objects.create_user(
        username="task-mutator", password="pass", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Runtime", objective="Boundary", owner=user
    )
    agent = Agent.objects.create(
        code="research", name="Research", mission="research", active=True
    )
    capability = AgentCapability.objects.create(
        code="research", name="Research", active=True
    )
    capability.agents.add(agent)

    from core.models import AgentTask

    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        action_type="research",
        capability_code="research",
        risk_snapshot="low",
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = getattr(client, method)(
        f"/api/tasks/{task.pk}/",
        {"action_type": "deploy"},
        format="json",
    )

    assert response.status_code == 405

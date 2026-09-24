import pytest
from django.contrib.auth import get_user_model
from core.models import ResearchProject
from core.services import normalize_action, requires_owner_approval


@pytest.mark.django_db
def test_approval_policy():
    assert requires_owner_approval("deploy", "high")
    assert requires_owner_approval(" production-change ", "low")
    assert requires_owner_approval("database migration", "low")
    assert not requires_owner_approval("research", "low")
    assert normalize_action(" production-change ") == "production_change"


@pytest.mark.django_db
def test_project():
    u = get_user_model().objects.create_user(username="owner")
    p = ResearchProject.objects.create(owner=u, title="Test", objective="Test")
    assert p.pk


@pytest.mark.django_db
def test_internal_api_requires_authentication():
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.get("/api/projects/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_internal_api_write_requires_staff():
    from rest_framework.test import APIClient

    user = get_user_model().objects.create_user(username="regular")
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/projects/",
        {"title": "Blocked", "objective": "Test", "owner": user.pk},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_staff_can_create_project():
    from rest_framework.test import APIClient

    user = get_user_model().objects.create_user(username="staff", is_staff=True)
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/projects/",
        {"title": "Allowed", "objective": "Test", "owner": user.pk},
        format="json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_task_claim_api_rejects_blocked_task():
    from rest_framework.test import APIClient
    from core.models import Agent, AgentTask

    user = get_user_model().objects.create_user(username="claim-owner", is_staff=True)
    agent = Agent.objects.create(code="claim-worker", name="Worker", mission="research", active=True)
    task = AgentTask.objects.create(agent=agent, status="blocked")
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(f"/api/tasks/{task.pk}/claim/", {}, format="json")
    assert response.status_code == 409

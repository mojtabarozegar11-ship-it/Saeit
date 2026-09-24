import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Agent, AgentCapability, ApprovalRequest, ResearchProject


@pytest.mark.django_db
def test_sensitive_flow_approval_claim_complete_and_audit():
    User = get_user_model()
    owner = User.objects.create_user(username="e2e-owner", password="pass", is_staff=True)
    project = ResearchProject.objects.create(title="Runtime E2E", objective="Controlled execution", owner=owner)
    agent = Agent.objects.create(code="deploy_e2e", name="Deploy", mission="deploy", active=True)
    capability = AgentCapability.objects.create(code="deploy_e2e", name="Deploy", risk_level="high", active=True)
    capability.agents.add(agent)

    client = APIClient()
    client.force_authenticate(user=owner)

    planned = client.post(
        "/api/master-chat/plan/",
        {
            "project_id": project.pk,
            "action_type": "deploy_e2e",
            "payload": {"target": "controlled"},
            "risk": "high",
        },
        format="json",
    )
    assert planned.status_code == 201
    task_id = planned.json()["id"]
    assert planned.json()["status"] == "blocked"

    approval = ApprovalRequest.objects.get(target_type="AgentTask", target_id=str(task_id))
    approved = client.post(
        f"/api/approvals/{approval.pk}/decide/",
        {"approved": True, "note": "Owner approved controlled execution"},
        format="json",
    )
    assert approved.status_code == 200

    claimed = client.post(f"/api/tasks/{task_id}/claim/", {}, format="json")
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "running"
    execution_id = claimed.json()["execution_id"]

    from core.task_runtime import TaskRuntime
    completed = TaskRuntime().complete(task_id, {"result": "controlled-success"}, execution_id=execution_id)
    assert completed.status == "completed"

    from core.models import AgentTask, AuditLog
    task = AgentTask.objects.get(pk=task_id)
    assert task.status == "completed"
    actions = set(AuditLog.objects.filter(target_type="AgentTask", target_id=str(task_id)).values_list("action", flat=True))
    assert "task_claimed" in actions
    assert "task_completed" in actions


@pytest.mark.django_db
def test_sensitive_flow_cannot_claim_before_approval():
    User = get_user_model()
    owner = User.objects.create_user(username="e2e-owner-2", password="pass", is_staff=True)
    project = ResearchProject.objects.create(title="Runtime E2E", objective="Approval gate", owner=owner)
    agent = Agent.objects.create(code="deploy_e2e_2", name="Deploy", mission="deploy", active=True)
    capability = AgentCapability.objects.create(code="deploy_e2e_2", name="Deploy", risk_level="high", active=True)
    capability.agents.add(agent)

    client = APIClient()
    client.force_authenticate(user=owner)
    planned = client.post(
        "/api/master-chat/plan/",
        {"project_id": project.pk, "action_type": "deploy_e2e_2", "risk": "high"},
        format="json",
    )
    assert planned.status_code == 201

    task_id = planned.json()["id"]
    assert client.post(f"/api/tasks/{task_id}/claim/", {}, format="json").status_code == 409

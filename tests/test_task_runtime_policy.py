import pytest
from django.contrib.auth import get_user_model
from core.models import Agent, AgentCapability, AgentTask, ApprovalRequest, ResearchProject
from core.task_runtime import TaskExecutionError, TaskRuntime

pytestmark = pytest.mark.django_db


def setup_task(risk="low"):
    owner = get_user_model().objects.create_user(username="runtime-owner")
    project = ResearchProject.objects.create(title="Runtime", objective="Test", owner=owner)
    agent = Agent.objects.create(code="runtime-agent", name="Runtime Agent", active=True)
    capability = AgentCapability.objects.create(code="run_task", name="Run task", risk_level=risk)
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, project=project, action_type="run_task", status="queued"
    )
    return owner, task


def test_high_risk_queued_task_cannot_bypass_approval_at_claim():
    _, task = setup_task("high")
    with pytest.raises(TaskExecutionError, match="approval"):
        TaskRuntime().claim(task.pk)


def test_high_risk_task_claims_after_approved_request():
    owner, task = setup_task("high")
    ApprovalRequest.objects.create(
        action_type="run_task",
        target_type="AgentTask",
        target_id=str(task.pk),
        reason="Approved execution",
        risk="high",
        status="approved",
        requested_by=owner,
    )
    claimed = TaskRuntime().claim(task.pk)
    assert claimed.status == "running"


def test_capability_deactivation_blocks_queued_task():
    _, task = setup_task("low")
    AgentCapability.objects.filter(code="run_task").update(active=False)
    with pytest.raises(TaskExecutionError, match="active capability"):
        TaskRuntime().claim(task.pk)

import pytest
from django.contrib.auth import get_user_model

from core.models import Agent, AgentCapability, AgentTask, ApprovalRequest, ResearchProject
from core.task_runtime import TaskExecutionError, TaskRuntime


def make_task(*, owner, action="research", risk="low", status="queued", max_attempts=3):
    project = ResearchProject.objects.create(title="Runtime", objective="Execution lifecycle", owner=owner)
    agent = Agent.objects.create(code=f"{action}_agent", name="Agent", mission=action, active=True)
    capability = AgentCapability.objects.create(code=action, name=action.title(), risk_level=risk, active=True)
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        action_type=action,
        capability_code=action,
        risk_snapshot=risk,
        status=status,
        max_attempts=max_attempts,
    )
    return task, agent


@pytest.mark.django_db
def test_claim_complete_creates_execution_and_finishes():
    owner = get_user_model().objects.create_user(username="runtime-owner", password="pass", is_staff=True)
    task, _ = make_task(owner=owner)

    claimed = TaskRuntime().claim(task.pk)
    assert claimed.status == "running"
    assert claimed.execution_id
    assert claimed.attempt_count == 1

    completed = TaskRuntime().complete(task.pk, {"result": "ok"}, cost=1.25)
    assert completed.status == "completed"
    assert completed.output_data == {"result": "ok"}


@pytest.mark.django_db
def test_high_risk_cannot_claim_without_approval():
    owner = get_user_model().objects.create_user(username="risk-owner", password="pass", is_staff=True)
    task, _ = make_task(owner=owner, action="deploy", risk="high")

    with pytest.raises(TaskExecutionError, match="approval"):
        TaskRuntime().claim(task.pk)

    task.refresh_from_db()
    assert task.status == "queued"
    assert task.attempt_count == 0


@pytest.mark.django_db
def test_failed_task_requeues_until_retry_budget_then_fails():
    owner = get_user_model().objects.create_user(username="retry-owner", password="pass", is_staff=True)
    task, _ = make_task(owner=owner, max_attempts=2)

    TaskRuntime().claim(task.pk)
    first = TaskRuntime().fail(task.pk, "temporary failure")
    assert first.status == "queued"
    assert first.attempt_count == 1

    TaskRuntime().claim(task.pk)
    second = TaskRuntime().fail(task.pk, "final failure")
    assert second.status == "failed"
    assert second.attempt_count == 2


@pytest.mark.django_db
def test_invalid_risk_snapshot_cannot_claim():
    owner = get_user_model().objects.create_user(
        username="invalid-risk-owner", password="pass", is_staff=True
    )
    task, _ = make_task(owner=owner, risk="low")
    task.risk_snapshot = "unsafe"
    task.save(update_fields=["risk_snapshot"])

    with pytest.raises(TaskExecutionError, match="risk snapshot is invalid"):
        TaskRuntime().claim(task.pk)

    task.refresh_from_db()
    assert task.status == "queued"
    assert task.attempt_count == 0

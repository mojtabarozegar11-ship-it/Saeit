import pytest
from django.contrib.auth import get_user_model

from core.models import Agent, AgentCapability, AgentTask, ResearchProject
from core.task_runtime import TaskRuntime


@pytest.mark.django_db
def test_retry_invalidates_previous_execution_identity():
    user = get_user_model().objects.create_user(
        username="retry-owner", password="pass", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Retry test", objective="Validate retry identity", owner=user
    )
    agent = Agent.objects.create(
        code="retry-agent", name="Retry Agent", mission="Retry safely", active=True
    )
    capability = AgentCapability.objects.create(
        code="retry", name="Retry", risk_level="low", active=True
    )
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, project=project, action_type="retry",
        capability_code="retry", risk_snapshot="low",
        status="running", execution_id="old-execution",
        attempt_count=1, max_attempts=3
    )

    TaskRuntime().fail(task.pk, "temporary worker failure", execution_id="old-execution")

    task.refresh_from_db()
    assert task.status == "queued"
    assert task.execution_id == ""

    claimed = TaskRuntime().claim(task.pk)
    assert claimed.status == "running"
    assert claimed.execution_id
    assert claimed.execution_id != "old-execution"


@pytest.mark.django_db
def test_final_failure_keeps_execution_identity_for_audit():
    user = get_user_model().objects.create_user(
        username="final-failure-owner", password="pass", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Final failure", objective="Validate terminal retry", owner=user
    )
    agent = Agent.objects.create(
        code="final-agent", name="Final Agent", mission="Fail safely", active=True
    )
    capability = AgentCapability.objects.create(
        code="final", name="Final", risk_level="low", active=True
    )
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, project=project, action_type="final",
        capability_code="final", risk_snapshot="low",
        status="running", execution_id="final-execution",
        attempt_count=3, max_attempts=3
    )

    TaskRuntime().fail(task.pk, "terminal failure", execution_id="final-execution")

    task.refresh_from_db()
    assert task.status == "failed"
    assert task.execution_id == "final-execution"

import pytest
from django.contrib.auth import get_user_model

from core.models import Agent, AgentCapability, AgentTask, ResearchProject
from core.task_runtime import TaskExecutionError, TaskRuntime


@pytest.mark.django_db
def test_legacy_failed_execution_is_held_for_handoff_without_replay():
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
    assert task.status == "blocked"
    assert task.execution_id == "old-execution"
    assert task.output_data["automatic_replay_allowed"] is False
    assert task.output_data["migration_target"] == "mojtaba-bot-ai"
    assert task.output_data["legacy_agent_code"] == "retry-agent"
    with pytest.raises(TaskExecutionError, match="blocked"):
        TaskRuntime().claim(task.pk)
    task.refresh_from_db()
    assert task.status == "blocked"
    assert task.execution_id == "old-execution"
    assert task.attempt_count == 1


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
    assert task.status == "blocked"
    assert task.execution_id == "final-execution"
    assert task.output_data["retry_budget_exhausted"] is True
    assert task.output_data["automatic_replay_allowed"] is False

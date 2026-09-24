import pytest
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Agent, AgentCapability, AgentTask, ResearchProject
from core.task_runtime import TaskExecutionError, TaskRuntime


@pytest.fixture
def stale_task(db):
    user = get_user_model().objects.create_user(
        username="recovery-owner", password="pass", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Recovery test", objective="Validate stale recovery", owner=user
    )
    agent = Agent.objects.create(
        code="recovery-agent", name="Recovery Agent",
        mission="Recover stale workers", active=True
    )
    capability = AgentCapability.objects.create(
        code="recovery", name="Recovery", risk_level="low", active=True
    )
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, project=project, action_type="recovery",
        capability_code="recovery", risk_snapshot="low",
        status="running", execution_id="stale-execution",
        attempt_count=1, max_attempts=3
    )
    AgentTask.objects.filter(pk=task.pk).update(
        updated_at=timezone.now() - timedelta(minutes=30)
    )
    return task


@pytest.mark.django_db
def test_heartbeat_requires_current_execution_identity(stale_task):
    runtime = TaskRuntime()
    runtime.heartbeat(stale_task.pk, "stale-execution")
    stale_task.refresh_from_db()
    assert stale_task.updated_at > timezone.now() - timedelta(seconds=5)

    with pytest.raises(TaskExecutionError, match="Execution identity"):
        runtime.heartbeat(stale_task.pk, "wrong-execution")


@pytest.mark.django_db
def test_recover_stale_requeues_and_invalidates_identity(stale_task):
    recovered = TaskRuntime().recover_stale(stale_task.pk, stale_after_seconds=60)
    assert recovered.status == "queued"
    assert recovered.execution_id == ""
    assert recovered.output_data["error"]


@pytest.mark.django_db
def test_recover_stale_refuses_fresh_execution(stale_task):
    stale_task.updated_at = timezone.now()
    stale_task.save(update_fields=["updated_at"])

    with pytest.raises(TaskExecutionError, match="not stale"):
        TaskRuntime().recover_stale(stale_task.pk, stale_after_seconds=60)


@pytest.mark.django_db
def test_recover_stale_exhausted_budget_becomes_failed(stale_task):
    stale_task.attempt_count = stale_task.max_attempts
    stale_task.save(update_fields=["attempt_count"])
    AgentTask.objects.filter(pk=stale_task.pk).update(
        updated_at=timezone.now() - timedelta(minutes=30)
    )

    recovered = TaskRuntime().recover_stale(stale_task.pk, stale_after_seconds=60)
    assert recovered.status == "failed"
    assert recovered.execution_id == "stale-execution"

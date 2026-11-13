import pytest
from django.contrib.auth import get_user_model
from core.models import Agent, AgentCapability, ResearchProject
from core.orchestrator import MasterAgent
from core.task_runtime import TaskExecutionError, TaskRuntime

pytestmark = pytest.mark.django_db


def setup_retry_task(max_attempts=3):
    owner = get_user_model().objects.create_user(username="retry-owner")
    project = ResearchProject.objects.create(title="Retry", objective="Test", owner=owner)
    agent = Agent.objects.create(code="mojtaba-bot-ai", name="Mojtaba.bot.ai", active=True)
    capability = AgentCapability.objects.create(code="retry_action", name="Retry", risk_level="low")
    capability.agents.add(agent)
    task = MasterAgent().plan(project, "retry_action", {})
    task.max_attempts = max_attempts
    task.save(update_fields=["max_attempts", "updated_at"])
    return task


def test_claim_creates_execution_identity_and_attempt():
    task = setup_retry_task()
    claimed = TaskRuntime().claim(task.pk)
    assert claimed.execution_id
    assert claimed.attempt_count == 1
    assert claimed.status == "running"


def test_failed_canonical_execution_never_retries_without_receipt_reconciliation():
    task = setup_retry_task(max_attempts=2)
    runtime = TaskRuntime()
    running = runtime.claim(task.pk)
    failed = runtime.fail(task.pk, "temporary error", execution_id=running.execution_id)
    assert failed.status == "blocked"
    assert failed.output_data["automatic_replay_allowed"] is False
    with pytest.raises(TaskExecutionError, match="blocked"):
        runtime.claim(task.pk)


def test_exhausted_retry_budget_cannot_be_claimed():
    task = setup_retry_task(max_attempts=1)
    runtime = TaskRuntime()
    running = runtime.claim(task.pk)
    runtime.fail(task.pk, "final error", execution_id=running.execution_id)
    with pytest.raises(TaskExecutionError, match="blocked"):
        runtime.claim(task.pk)

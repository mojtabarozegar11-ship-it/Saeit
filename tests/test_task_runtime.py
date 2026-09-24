import pytest
from django.contrib.auth import get_user_model
from core.models import Agent, AgentTask, ResearchProject
from core.task_runtime import TaskExecutionError, TaskRuntime

pytestmark = pytest.mark.django_db


def setup_task(active=True, status="queued"):
    user = get_user_model().objects.create_user(username="task-owner")
    project = ResearchProject.objects.create(title="Task Project", objective="Test", owner=user)
    agent = Agent.objects.create(
        code="worker", name="Worker", mission="research", active=active
    )
    task = AgentTask.objects.create(
        agent=agent, project=project, status=status, input_data={"x": 1}
    )
    return task


def test_blocked_task_cannot_be_claimed():
    task = setup_task(status="blocked")
    with pytest.raises(TaskExecutionError, match="blocked"):
        TaskRuntime().claim(task.pk)


def test_queued_task_can_be_claimed_and_completed():
    task = setup_task()
    runtime = TaskRuntime()
    running = runtime.claim(task.pk)
    assert running.status == "running"
    completed = runtime.complete(task.pk, {"answer": "ok"}, cost="0.1250")
    assert completed.status == "completed"
    assert completed.output_data == {"answer": "ok"}


def test_inactive_agent_cannot_run_task():
    task = setup_task(active=False)
    with pytest.raises(TaskExecutionError, match="inactive"):
        TaskRuntime().claim(task.pk)


def test_completed_task_cannot_be_claimed_again():
    task = setup_task()
    runtime = TaskRuntime()
    runtime.claim(task.pk)
    runtime.complete(task.pk, {"done": True})
    with pytest.raises(TaskExecutionError, match="completed"):
        runtime.claim(task.pk)


def test_running_task_can_fail_and_records_error():
    task = setup_task()
    runtime = TaskRuntime()
    runtime.claim(task.pk)
    failed = runtime.fail(task.pk, "provider timeout")
    assert failed.status == "failed"
    assert failed.output_data["error"] == "provider timeout"

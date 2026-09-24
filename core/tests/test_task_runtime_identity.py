import pytest
from django.contrib.auth import get_user_model

from core.models import Agent, AgentCapability, AgentTask, ResearchProject
from core.task_runtime import TaskExecutionError, TaskRuntime


@pytest.mark.django_db
def test_stale_execution_identity_cannot_complete_task():
    owner = get_user_model().objects.create_user(username="identity-owner", password="pass")
    project = ResearchProject.objects.create(title="Identity", objective="Worker", owner=owner)
    agent = Agent.objects.create(code="identity-agent", name="Identity", mission="identity", active=True)
    capability = AgentCapability.objects.create(code="identity", name="Identity", active=True)
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, project=project, action_type="identity",
        capability_code="identity", risk_snapshot="low",
    )

    claimed = TaskRuntime().claim(task.pk)

    with pytest.raises(TaskExecutionError, match="Execution identity"):
        TaskRuntime().complete(task.pk, {"ok": True}, execution_id="stale-execution")

    task.refresh_from_db()
    assert task.status == "running"
    assert task.execution_id == claimed.execution_id

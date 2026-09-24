import json

import pytest
from django.core.management import call_command

from core.models import Agent, AgentCapability, AgentTask, ResearchProject
from core.task_runtime import TaskRuntime


pytestmark = pytest.mark.django_db


def test_recover_stale_tasks_command_reports_summary(capsys):
    project = ResearchProject.objects.create(
        title="Recovery command",
        objective="Validate scheduled recovery",
        owner_id=None,
    )
    agent = Agent.objects.create(
        code="recovery-worker",
        name="Recovery Worker",
        mission="recover stale tasks",
        active=True,
        risk_level="low",
    )
    capability = AgentCapability.objects.create(
        code="research",
        name="Research",
        active=True,
        risk_level="low",
    )
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        action_type="research",
        capability_code="research",
        risk_snapshot="low",
        status="queued",
    )
    running = TaskRuntime().claim(task.pk)
    AgentTask.objects.filter(pk=task.pk).update(
        updated_at=task.updated_at.replace(year=2000)
    )

    call_command("recover_stale_tasks", "--stale-after", "60")
    payload = json.loads(capsys.readouterr().out)

    assert payload["scanned"] == 1
    assert payload["recovered"] == 1
    task.refresh_from_db()
    assert task.status == "queued"
    assert task.execution_id == ""

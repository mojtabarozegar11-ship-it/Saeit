import pytest
from django.contrib.auth import get_user_model
from core.models import Agent, AgentCapability, ResearchProject
from core.orchestrator import MasterAgent
from core.task_runtime import TaskExecutionError, TaskRuntime

pytestmark = pytest.mark.django_db


def setup_snapshot_task():
    owner = get_user_model().objects.create_user(username="snapshot-owner")
    project = ResearchProject.objects.create(title="Snapshot", objective="Test", owner=owner)
    agent = Agent.objects.create(code="snapshot-agent", name="Snapshot Agent", active=True)
    capability = AgentCapability.objects.create(
        code="snapshot_action", name="Snapshot Action", risk_level="low"
    )
    capability.agents.add(agent)
    return project, agent, capability


def test_task_persists_capability_and_risk_snapshot():
    project, _, capability = setup_snapshot_task()
    task = MasterAgent().plan(project, "snapshot_action", {}, risk="low")
    assert task.capability_code == capability.code
    assert task.risk_snapshot == "low"


def test_risk_change_after_planning_blocks_execution():
    project, _, capability = setup_snapshot_task()
    task = MasterAgent().plan(project, "snapshot_action", {}, risk="low")
    capability.risk_level = "high"
    capability.save(update_fields=["risk_level", "updated_at"])
    with pytest.raises(TaskExecutionError, match="risk policy"):
        TaskRuntime().claim(task.pk)


def test_capability_code_mismatch_blocks_execution():
    project, _, capability = setup_snapshot_task()
    task = MasterAgent().plan(project, "snapshot_action", {}, risk="low")
    capability.code = "changed_action"
    capability.save(update_fields=["code", "updated_at"])
    with pytest.raises(TaskExecutionError, match="active capability"):
        TaskRuntime().claim(task.pk)

"""Stale work must never silently replay a possibly completed economic action."""

import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.models import Agent, AgentCapability, AgentTask, AuditLog
from core.task_runtime import TaskExecutionError, TaskRuntime


@pytest.fixture
def economic_agent(db):
    agent = Agent.objects.create(
        code="economic-master-agent", name="Mojtaba.bot executor",
        mission="Bounded economic execution", active=True,
    )
    cap = AgentCapability.objects.create(
        code="income_market_research", name="Market research", risk_level="low", active=True,
    )
    cap.agents.add(agent)
    return agent, cap


def running_economic_task(agent, cap, *, attempts=1, max_attempts=3):
    task = AgentTask.objects.create(
        agent=agent, action_type=cap.code, capability_code=cap.code,
        risk_snapshot="low", status="running", execution_id="prior-identity",
        attempt_count=attempts, max_attempts=max_attempts,
    )
    AgentTask.objects.filter(pk=task.pk).update(
        updated_at=timezone.now() - timedelta(minutes=45)
    )
    return task


def test_stale_economic_execution_is_blocked_without_automatic_replay(economic_agent):
    agent, cap = economic_agent
    task = running_economic_task(agent, cap)

    recovered = TaskRuntime().recover_stale(task.pk, stale_after_seconds=900)

    assert recovered.status == "blocked"
    assert recovered.execution_id == "prior-identity"
    assert recovered.attempt_count == 1
    assert recovered.output_data["requires_review"] is True
    assert recovered.output_data["automatic_replay_allowed"] is False
    assert recovered.output_data["previous_execution_id"] == "prior-identity"
    audit = AuditLog.objects.get(target_type="AgentTask", target_id=str(task.pk), action="task_recovered_stale")
    assert audit.after_state["requires_review"] is True


def test_recovery_command_reports_blocked_once_and_is_idempotent(economic_agent):
    agent, cap = economic_agent
    task = running_economic_task(agent, cap)
    output = StringIO()
    call_command("recover_stale_tasks", agent_code=agent.code, stdout=output)
    result = json.loads(output.getvalue())
    assert result["scanned"] == 1
    assert result["blocked"] == 1
    assert result["recovered"] == 0

    output = StringIO()
    call_command("recover_stale_tasks", agent_code=agent.code, stdout=output)
    second = json.loads(output.getvalue())
    assert second["scanned"] == 0
    assert second["blocked"] == 0
    task.refresh_from_db()
    assert task.status == "blocked"
    assert task.attempt_count == 1


def test_exhausted_economic_retries_remain_terminal_failed(economic_agent):
    agent, cap = economic_agent
    task = running_economic_task(agent, cap, attempts=3, max_attempts=3)
    result = TaskRuntime().recover_stale(task.pk, stale_after_seconds=900)
    assert result.status == "failed"
    assert result.execution_id == "prior-identity"


def test_non_economic_stale_work_keeps_existing_requeue_policy(db):
    agent = Agent.objects.create(code="ordinary-research", name="Research", mission="Research", active=True)
    task = AgentTask.objects.create(
        agent=agent, action_type="research", capability_code="research", status="running",
        execution_id="research-identity", attempt_count=1,
    )
    AgentTask.objects.filter(pk=task.pk).update(
        updated_at=timezone.now() - timedelta(minutes=45)
    )
    result = TaskRuntime().recover_stale(task.pk, stale_after_seconds=900)
    assert result.status == "queued"
    assert result.execution_id == ""


def test_two_economic_tasks_cannot_be_running_together(economic_agent):
    agent, cap = economic_agent
    queued = [
        AgentTask.objects.create(
            agent=agent, action_type=cap.code, capability_code=cap.code,
            risk_snapshot="low", status="queued",
        )
        for _ in range(2)
    ]
    first = TaskRuntime().claim(queued[0].pk)
    with pytest.raises(TaskExecutionError, match="already has a running task"):
        TaskRuntime().claim(queued[1].pk)
    queued[1].refresh_from_db()
    assert queued[1].status == "queued"
    assert queued[1].attempt_count == 0
    TaskRuntime().fail(first.pk, "interrupted", execution_id=first.execution_id)
    assert TaskRuntime().claim(queued[1].pk).status == "running"


def test_worker_reports_existing_execution_without_dispatch(economic_agent):
    agent, cap = economic_agent
    running = AgentTask.objects.create(
        agent=agent, action_type=cap.code, capability_code=cap.code,
        risk_snapshot="low", status="queued",
    )
    TaskRuntime().claim(running.pk)
    output = StringIO()
    with patch("core.management.commands.run_economic_worker.WorkerRunner") as runner:
        call_command("run_economic_worker", stdout=output)
        runner.assert_not_called()
    assert f"WAIT_RUNNING task={running.pk}" in output.getvalue()


def test_master_loop_does_not_replan_while_economic_work_runs(economic_agent):
    agent, cap = economic_agent
    running = AgentTask.objects.create(
        agent=agent, action_type=cap.code, capability_code=cap.code,
        risk_snapshot="low", status="queued",
    )
    TaskRuntime().claim(running.pk)
    output = StringIO()
    with patch("core.management.commands.autonomous_master_loop.call_command") as planner, patch(
        "core.management.commands.autonomous_master_loop.WorkerRunner"
    ) as runner:
        call_command("autonomous_master_loop", max_steps=3, stdout=output)
        planner.assert_not_called()
        runner.assert_not_called()
    assert f"AUTO_WAIT_RUNNING task={running.pk}" in output.getvalue()

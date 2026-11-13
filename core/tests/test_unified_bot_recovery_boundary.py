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
        code="mojtaba-bot-ai", name="Mojtaba.bot executor",
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


def test_exhausted_economic_stale_work_remains_blocked_for_receipt_review(economic_agent):
    agent, cap = economic_agent
    task = running_economic_task(agent, cap, attempts=3, max_attempts=3)
    result = TaskRuntime().recover_stale(task.pk, stale_after_seconds=900)
    assert result.status == "blocked"
    assert result.execution_id == "prior-identity"
    assert result.output_data["requires_review"] is True
    assert result.output_data["automatic_replay_allowed"] is False
    assert result.output_data["retry_budget_exhausted"] is True
    with pytest.raises(TaskExecutionError, match="blocked"):
        TaskRuntime().claim(task.pk)


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



@pytest.mark.parametrize("max_attempts", [1, 3])
def test_canonical_worker_failure_never_requeues_unknown_effect(economic_agent, max_attempts):
    agent, cap = economic_agent
    task = AgentTask.objects.create(
        agent=agent, action_type=cap.code, capability_code=cap.code,
        risk_snapshot="low", status="queued", max_attempts=max_attempts,
    )
    runtime = TaskRuntime()
    running = runtime.claim(task.pk)
    token = running.execution_id

    blocked = runtime.fail(task.pk, "provider acknowledgement lost", execution_id=token)
    assert blocked.status == "blocked"
    assert blocked.execution_id == token
    assert blocked.attempt_count == 1
    assert blocked.output_data["requires_review"] is True
    assert blocked.output_data["automatic_replay_allowed"] is False
    assert blocked.output_data["previous_execution_id"] == token
    assert blocked.output_data["retry_budget_exhausted"] is (max_attempts == 1)
    with pytest.raises(TaskExecutionError, match="blocked"):
        runtime.claim(task.pk)
    with pytest.raises(TaskExecutionError, match="not running"):
        runtime.complete(task.pk, {"verified_effect": True}, execution_id=token)
    receipt = AuditLog.objects.get(
        action="task_failed", target_type="AgentTask", target_id=str(task.pk),
    )
    assert receipt.after_state["requires_review"] is True
    assert receipt.after_state["automatic_replay_allowed"] is False


def test_noncanonical_worker_failure_still_preserves_existing_retry_contract(db):
    agent = Agent.objects.create(
        code="ordinary-worker", name="Ordinary", mission="Legacy", active=True,
    )
    cap = AgentCapability.objects.create(
        code="ordinary-research", name="Ordinary research",
        risk_level="low", active=True,
    )
    cap.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, action_type=cap.code, capability_code=cap.code,
        risk_snapshot="low", status="queued", max_attempts=2,
    )
    runtime = TaskRuntime()
    first = runtime.claim(task.pk)
    queued = runtime.fail(task.pk, "temporary error", execution_id=first.execution_id)
    assert queued.status == "queued"
    assert queued.execution_id == ""
    second = runtime.claim(task.pk)
    final = runtime.fail(task.pk, "final error", execution_id=second.execution_id)
    assert final.status == "failed"
    assert final.execution_id == second.execution_id

def test_failed_gateway_with_unknown_external_effect_is_not_dispatched_twice(economic_agent):
    """An acknowledgement failure after a side effect cannot trigger replay."""
    from core.worker_runner import WorkerRunner

    agent, cap = economic_agent
    task = AgentTask.objects.create(
        agent=agent, action_type=cap.code, capability_code=cap.code,
        risk_snapshot="low", status="queued", max_attempts=5,
    )
    effects = []

    class AcknowledgementLostGateway:
        def invoke(self, code, payload, *, task_id, execution_id):
            effects.append((code, task_id, execution_id))
            raise RuntimeError("effect receipt unavailable after dispatch")

    worker = WorkerRunner(AcknowledgementLostGateway())
    with pytest.raises(RuntimeError, match="receipt unavailable"):
        worker.run(task.pk)
    task.refresh_from_db()
    assert task.status == "blocked"
    assert task.output_data["automatic_replay_allowed"] is False
    assert len(effects) == 1

    with pytest.raises(TaskExecutionError, match="blocked"):
        worker.run(task.pk)
    assert len(effects) == 1
    assert AuditLog.objects.filter(
        target_type="AgentTask", target_id=str(task.pk), action="task_failed",
    ).count() == 1


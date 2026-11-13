"""No stale master task may stay alive or complete after an identity handoff.

All fixtures use Django's test database. No external trade, deployment,
payments, emails or real side effects are exercised.
"""
import pytest

from core.models import Agent, AgentCapability, AgentTask, AuditLog
from core.task_runtime import TaskRuntime, TaskExecutionError


pytestmark = pytest.mark.django_db
PROOF = {
    "action_performed": "Reviewed an internal immutable record",
    "verified_effect": True,
    "evidence": {"kind": "test_fixture", "value": "private"},
}


def master_setup():
    cap = AgentCapability.objects.create(
        code="income_market_research", name="Private inventory",
        risk_level="low", active=True,
    )
    old = Agent.objects.create(
        code="economic-master-agent", name="Prior master", mission="Research",
        active=True,
    )
    old.capabilities.add(cap)
    queued = AgentTask.objects.create(
        agent=old, action_type=cap.code, capability_code=cap.code,
        risk_snapshot="low", status="queued",
    )
    return old, cap, queued


def canonical(cap):
    row = Agent.objects.create(
        code="mojtaba-bot-ai", name="Mojtaba.bot.ai",
        mission="One runtime", active=True,
    )
    row.capabilities.add(cap)
    return row


def test_inflight_task_cannot_complete_after_second_master_activates():
    _, cap, task = master_setup()
    claimed = TaskRuntime().claim(task.pk)
    canonical(cap)
    before = (AuditLog.objects.count(), task.cost)
    with pytest.raises(TaskExecutionError, match="MASTER_TASK_MULTIPLE_ACTIVE_RUNTIMES"):
        TaskRuntime().complete(task.pk, PROOF, cost="2.5", execution_id=claimed.execution_id)
    task.refresh_from_db()
    assert task.status == "running"
    assert task.output_data != PROOF
    assert task.cost == before[1]
    assert AuditLog.objects.count() == before[0]


def test_inflight_task_cannot_heartbeat_with_parallel_master():
    _, cap, task = master_setup()
    claimed = TaskRuntime().claim(task.pk)
    task.refresh_from_db()
    timestamp = task.updated_at
    canonical(cap)
    with pytest.raises(TaskExecutionError, match="MASTER_TASK_MULTIPLE_ACTIVE_RUNTIMES"):
        TaskRuntime().heartbeat(task.pk, execution_id=claimed.execution_id)
    task.refresh_from_db()
    assert task.updated_at == timestamp
    assert task.status == "running"


def test_old_master_cannot_finalize_after_switch_to_canonical():
    old, cap, task = master_setup()
    claimed = TaskRuntime().claim(task.pk)
    old.active = False
    old.save(update_fields=["active"])
    canonical(cap)
    with pytest.raises(TaskExecutionError, match="MASTER_TASK_NOT_OWNED_BY_ACTIVE_RUNTIME"):
        TaskRuntime().complete(task.pk, PROOF, execution_id=claimed.execution_id)
    with pytest.raises(TaskExecutionError, match="MASTER_TASK_NOT_OWNED_BY_ACTIVE_RUNTIME"):
        TaskRuntime().heartbeat(task.pk, execution_id=claimed.execution_id)
    task.refresh_from_db()
    assert task.status == "running"


def test_single_canonical_runtime_can_heartbeat_and_complete_without_restarting_old_task():
    old, cap, old_task = master_setup()
    old.active = False
    old.save(update_fields=["active"])
    current = canonical(cap)
    task = AgentTask.objects.create(
        agent=current, action_type=cap.code, capability_code=cap.code,
        risk_snapshot="low", status="queued",
    )
    claimed = TaskRuntime().claim(task.pk)
    assert TaskRuntime().heartbeat(task.pk, claimed.execution_id).status == "running"
    finished = TaskRuntime().complete(
        task.pk, PROOF, cost="0", execution_id=claimed.execution_id,
    )
    assert finished.status == "completed"
    assert finished.output_data == PROOF
    old_task.refresh_from_db()
    assert old_task.status == "queued"
    assert old_task.attempt_count == 0


def test_generic_specialist_lifecycle_does_not_depend_on_master_conflict():
    _, cap, _ = master_setup()
    canonical(cap)
    specialist = Agent.objects.create(
        code="independent-specialist", name="Independent",
        mission="Unrelated research", active=True,
    )
    research = AgentCapability.objects.create(
        code="research", name="Research", risk_level="low", active=True,
    )
    specialist.capabilities.add(research)
    task = AgentTask.objects.create(
        agent=specialist, action_type="research",
        capability_code="research", risk_snapshot="low", status="queued",
    )
    claimed = TaskRuntime().claim(task.pk)
    TaskRuntime().heartbeat(task.pk, claimed.execution_id)
    finished = TaskRuntime().complete(
        task.pk, {"result": "done"}, execution_id=claimed.execution_id,
    )
    assert finished.status == "completed"


def test_failed_old_master_can_be_recorded_for_safety_after_handoff():
    old, cap, task = master_setup()
    claimed = TaskRuntime().claim(task.pk)
    old.active = False
    old.save(update_fields=["active"])
    canonical(cap)
    # Failure recording and bounded recovery must remain available even when
    # success cannot be falsely certified.
    result = TaskRuntime().fail(
        task.pk, "Identity handoff interrupted work",
        execution_id=claimed.execution_id,
    )
    assert result.status in ("queued", "failed")
    assert "Identity handoff" in result.output_data["error"]

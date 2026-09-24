import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from core.models import Agent, AgentTask, AuditLog
from core.observability import RuntimeObservability


@pytest.fixture
def task_factory(db):
    agent = Agent.objects.create(
        code="metrics-agent",
        name="Metrics Agent",
        mission="Metrics tests",
        active=True,
        risk_level="low",
    )

    def make(**overrides):
        values = {
            "agent": agent,
            "action_type": "research",
            "capability_code": "research",
            "risk_snapshot": "low",
            "input_data": {},
            "cost": Decimal("1.2500"),
        }
        values.update(overrides)
        return AgentTask.objects.create(**values)

    return make


def test_snapshot_counts_statuses_and_cost(task_factory):
    task_factory(status="queued")
    task_factory(status="running")
    task_factory(status="completed")
    task_factory(status="failed")
    task_factory(status="cancelled")

    metrics = RuntimeObservability().snapshot()

    assert metrics.queued == 1
    assert metrics.running == 1
    assert metrics.completed == 1
    assert metrics.failed == 1
    assert metrics.cancelled == 1
    assert metrics.total_cost == Decimal("6.2500")


def test_snapshot_detects_stale_running_tasks(task_factory):
    task = task_factory(status="running")
    AgentTask.objects.filter(pk=task.pk).update(
        updated_at=timezone.now() - timedelta(seconds=901)
    )

    metrics = RuntimeObservability().snapshot(stale_after_seconds=900)

    assert metrics.stale_running == 1


def test_audit_count_can_filter_action(task_factory):
    task = task_factory()
    AuditLog.objects.create(
        actor_type="agent",
        actor_id=str(task.agent_id),
        action="task_completed",
        target_type="AgentTask",
        target_id=str(task.pk),
        trace_id="trace-1",
    )
    AuditLog.objects.create(
        actor_type="agent",
        actor_id=str(task.agent_id),
        action="task_failed",
        target_type="AgentTask",
        target_id=str(task.pk),
        trace_id="trace-2",
    )

    metrics = RuntimeObservability()
    assert metrics.audit_count() == 2
    assert metrics.audit_count("task_completed") == 1


@pytest.mark.parametrize("value", [0, -1, True, False, "900", None])
def test_snapshot_rejects_invalid_stale_after(task_factory, value):
    with pytest.raises(ValueError):
        RuntimeObservability().snapshot(stale_after_seconds=value)

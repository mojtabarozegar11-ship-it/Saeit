import pytest

from core.models import Agent, AgentTask
from core.recovery_scheduler import RecoveryScheduler


@pytest.fixture
def running_task(db):
    agent = Agent.objects.create(
        code="recovery-agent",
        name="Recovery Agent",
        mission="Own stale task recovery",
        active=True,
        risk_level="low",
    )
    return AgentTask.objects.create(
        agent=agent,
        action_type="research",
        capability_code="research",
        risk_snapshot="low",
        status="running",
        execution_id="exec-1",
        max_attempts=2,
    )


class StubRuntime:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = []

    def recover_stale(self, task_id, stale_after_seconds):
        self.calls.append((task_id, stale_after_seconds))
        outcome = self.outcomes[task_id]
        if isinstance(outcome, Exception):
            raise outcome
        task = AgentTask.objects.get(pk=task_id)
        task.status = outcome
        task.execution_id = "" if outcome == "queued" else task.execution_id
        task.save(update_fields=["status", "execution_id", "updated_at"])
        return task


def test_recovery_scheduler_is_bounded_and_delegates(running_task):
    second = AgentTask.objects.create(
        agent=running_task.agent,
        action_type="research",
        capability_code="research",
        risk_snapshot="low",
        status="running",
        execution_id="exec-2",
    )
    runtime = StubRuntime({running_task.pk: "queued", second.pk: "failed"})

    summary = RecoveryScheduler(runtime).recover(
        limit=1, stale_after_seconds=300
    )

    assert summary.scanned == 1
    assert summary.recovered == 1
    assert summary.failed == 0
    assert runtime.calls == [(running_task.pk, 300)]


def test_recovery_scheduler_classifies_exhausted_tasks(running_task):
    runtime = StubRuntime({running_task.pk: "failed"})

    summary = RecoveryScheduler(runtime).recover()

    assert summary.failed == 1
    assert summary.recovered == 0


def test_recovery_scheduler_records_errors(running_task):
    runtime = StubRuntime({running_task.pk: RuntimeError("race")})

    summary = RecoveryScheduler(runtime).recover()

    assert summary.skipped == 1
    assert "race" in summary.errors[0]


@pytest.mark.parametrize("limit", [0, -1, True, False, "2", None])
def test_recovery_scheduler_rejects_invalid_limit(running_task, limit):
    with pytest.raises(ValueError):
        RecoveryScheduler().recover(limit=limit)


@pytest.mark.parametrize("value", [0, -1, True, False, "900", None])
def test_recovery_scheduler_rejects_invalid_stale_after(running_task, value):
    with pytest.raises(ValueError):
        RecoveryScheduler().recover(stale_after_seconds=value)

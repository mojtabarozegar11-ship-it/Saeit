import pytest

from core.models import Agent, AgentCapability, AgentTask
from core.queue_dispatcher import QueueDispatcher
from core.task_runtime import TaskExecutionError
from core.unified_bot_identity import BOT_CODE


@pytest.fixture
def task_factory(db):
    agent = Agent.objects.create(
        code=BOT_CODE,
        name="Dispatcher Agent",
        mission="Dispatch queued tasks",
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

    def make(**overrides):
        values = {
            "agent": agent,
            "action_type": "research",
            "capability_code": "research",
            "risk_snapshot": "low",
            "input_data": {"q": "test"},
        }
        values.update(overrides)
        return AgentTask.objects.create(**values)

    return make


class StubRunner:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = []

    def run(self, task_id):
        self.calls.append(task_id)
        outcome = self.outcomes[task_id]
        if isinstance(outcome, Exception):
            raise outcome
        task = AgentTask.objects.get(pk=task_id)
        task.status = outcome
        task.save(update_fields=["status", "updated_at"])
        return task


def test_dispatch_respects_limit_and_order(task_factory):
    first = task_factory()
    second = task_factory()
    third = task_factory()
    runner = StubRunner({
        first.pk: "completed",
        second.pk: "completed",
        third.pk: "completed",
    })

    summary = QueueDispatcher(runner).dispatch(limit=2)

    assert summary.scanned == 2
    assert runner.calls == [first.pk, second.pk]
    assert summary.completed == 2


def test_dispatch_classifies_completed_and_retried(task_factory):
    completed = task_factory()
    retrying = task_factory()
    runner = StubRunner({
        completed.pk: "completed",
        retrying.pk: RuntimeError("temporary"),
    })

    summary = QueueDispatcher(runner).dispatch(limit=2)

    assert summary.completed == 1
    assert summary.retried == 1
    assert summary.failed == 0
    assert len(summary.errors) == 1


def test_dispatch_classifies_failed(task_factory):
    failed = task_factory()
    runner = StubRunner({failed.pk: "failed"})

    summary = QueueDispatcher(runner).dispatch()

    assert summary.failed == 1
    assert summary.retried == 0


def test_dispatch_skips_claim_errors(task_factory):
    task = task_factory()
    runner = StubRunner({task.pk: TaskExecutionError("approval required")})

    summary = QueueDispatcher(runner).dispatch()

    assert summary.skipped == 1
    assert summary.errors
    assert "approval required" in summary.errors[0]


@pytest.mark.parametrize("limit", [0, -1, True, False, "2", None])
def test_dispatch_rejects_invalid_limit(task_factory, limit):
    runner = StubRunner({})
    with pytest.raises(ValueError):
        QueueDispatcher(runner).dispatch(limit=limit)



def test_legacy_pending_task_is_not_passed_even_to_custom_runner(task_factory):
    from core.models import Agent
    canonical_task = task_factory()
    old = Agent.objects.create(
        code="old-queue-executor", name="Old private worker",
        mission="Unmerged historical tasks", active=True,
    )
    legacy = task_factory(agent=old)
    runner = StubRunner({
        canonical_task.pk: "completed",
        legacy.pk: "completed",
    })
    summary = QueueDispatcher(runner).dispatch(limit=5)
    legacy.refresh_from_db()
    assert summary.scanned == 1
    assert summary.completed == 1
    assert runner.calls == [canonical_task.pk]
    assert legacy.agent_id == old.pk
    assert legacy.status == "queued"


def test_only_active_canonical_owner_is_dispatchable(task_factory):
    task = task_factory()
    task.agent.active = False
    task.agent.save(update_fields=["active"])
    runner = StubRunner({task.pk: "completed"})
    summary = QueueDispatcher(runner).dispatch()
    assert summary.scanned == 0 and summary.completed == 0
    assert runner.calls == []
    task.refresh_from_db()
    assert task.status == "queued"

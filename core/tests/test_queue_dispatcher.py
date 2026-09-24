import pytest

from core.models import Agent, AgentCapability, AgentTask
from core.queue_dispatcher import QueueDispatcher
from core.task_runtime import TaskExecutionError


@pytest.fixture
def task_factory(db):
    agent = Agent.objects.create(
        code="dispatcher-agent",
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
        return AgentTask.objects.get(pk=task_id)


def test_dispatch_respects_limit_and_order(task_factory):
    first = task_factory()
    second = task_factory()
    third = task_factory()
    runner = StubRunner({first.pk: first, second.pk: second, third.pk: third})

    summary = QueueDispatcher(runner).dispatch(limit=2)

    assert summary.scanned == 2
    assert runner.calls == [first.pk, second.pk]


def test_dispatch_classifies_completed_and_retried(task_factory):
    completed = task_factory(status="completed")
    retrying = task_factory()
    runner = StubRunner({
        completed.pk: completed,
        retrying.pk: RuntimeError("temporary"),
    })

    summary = QueueDispatcher(runner).dispatch(limit=2)

    assert summary.completed == 1
    assert summary.retried == 1
    assert summary.failed == 0
    assert len(summary.errors) == 1


def test_dispatch_classifies_failed(task_factory):
    failed = task_factory()
    failed.status = "failed"
    failed.save(update_fields=["status", "updated_at"])
    runner = StubRunner({failed.pk: RuntimeError("permanent")})

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

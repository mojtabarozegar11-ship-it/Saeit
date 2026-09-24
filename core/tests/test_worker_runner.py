import pytest
from django.contrib.auth import get_user_model

from core.models import Agent, AgentCapability, AgentTask, ResearchProject
from core.task_runtime import TaskExecutionError
from core.tool_gateway import ToolGateway, ToolSpec
from core.worker_runner import WorkerRunner, WorkerRunnerError


@pytest.fixture
def queued_task(db):
    user = get_user_model().objects.create_user(
        username="worker-owner", password="pass", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Worker test", objective="Validate runner", owner=user
    )
    agent = Agent.objects.create(
        code="worker-agent",
        name="Worker Agent",
        mission="Execute queued work",
        risk_level="low",
        active=True,
    )
    capability = AgentCapability.objects.create(
        code="research",
        name="Research",
        risk_level="low",
        active=True,
    )
    capability.agents.add(agent)
    return AgentTask.objects.create(
        agent=agent,
        project=project,
        action_type="research",
        capability_code="research",
        risk_snapshot="low",
        input_data={"q": "wheat"},
        max_attempts=2,
    )


def test_runner_claims_invokes_and_completes(queued_task):
    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda payload: {
            "answer": payload["q"],
            "__cost": "1.2500",
        }),
    ])

    task = WorkerRunner(gateway).run(queued_task.pk)

    assert task.status == "completed"
    assert task.output_data == {"answer": "wheat"}
    assert str(task.cost) == "1.2500"
    assert task.attempt_count == 1
    assert task.execution_id


def test_runner_requeues_after_tool_failure(queued_task):
    def explode(payload):
        raise RuntimeError("tool exploded")

    gateway = ToolGateway([ToolSpec(code="research", handler=explode)])

    with pytest.raises(RuntimeError, match="tool exploded"):
        WorkerRunner(gateway).run(queued_task.pk)

    queued_task.refresh_from_db()
    assert queued_task.status == "queued"
    assert queued_task.execution_id == ""
    assert queued_task.attempt_count == 1
    assert "tool exploded" in queued_task.output_data["error"]


def test_runner_fails_when_retry_budget_is_exhausted(queued_task):
    queued_task.max_attempts = 1
    queued_task.save(update_fields=["max_attempts", "updated_at"])

    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda payload: (_ for _ in ()).throw(
            RuntimeError("permanent failure")
        )),
    ])

    with pytest.raises(RuntimeError, match="permanent failure"):
        WorkerRunner(gateway).run(queued_task.pk)

    queued_task.refresh_from_db()
    assert queued_task.status == "failed"
    assert queued_task.execution_id


def test_runner_supports_explicit_tool_mapping(queued_task):
    gateway = ToolGateway([
        ToolSpec(code="research_lookup", handler=lambda payload: {"found": payload["q"]}),
    ])

    task = WorkerRunner(
        gateway,
        tool_map={"research": "research_lookup"},
    ).run(queued_task.pk)

    assert task.status == "completed"
    assert task.output_data == {"found": "wheat"}


def test_runner_rejects_non_object_input(queued_task):
    queued_task.input_data = ["invalid"]
    queued_task.save(update_fields=["input_data", "updated_at"])
    gateway = ToolGateway([ToolSpec(code="research", handler=lambda payload: payload)])

    with pytest.raises(WorkerRunnerError, match="input"):
        WorkerRunner(gateway).run(queued_task.pk)

    queued_task.refresh_from_db()
    assert queued_task.status == "queued"


def test_runner_rejects_invalid_tool_cost(queued_task):
    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda payload: {"__cost": "NaN"}),
    ])

    with pytest.raises(WorkerRunnerError, match="cost"):
        WorkerRunner(gateway).run(queued_task.pk)

    queued_task.refresh_from_db()
    assert queued_task.status == "queued"


def test_runner_propagates_lifecycle_errors(queued_task):
    queued_task.status = "cancelled"
    queued_task.save(update_fields=["status", "updated_at"])
    gateway = ToolGateway([ToolSpec(code="research", handler=lambda payload: payload)])

    with pytest.raises(TaskExecutionError, match="status"):
        WorkerRunner(gateway).run(queued_task.pk)

    queued_task.refresh_from_db()
    assert queued_task.status == "cancelled"

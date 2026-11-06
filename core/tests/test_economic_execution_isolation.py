"""Economic work must remain valid with the factory runtime ABI unavailable."""

from unittest.mock import patch

import pytest

from core.economic_execution import EconomicExecutionError, EconomicWorkerRunner
from core.economic_tool_pack import build_economic_master_gateway, build_economic_gateway
from core.models import Agent, AgentCapability, AgentTask


def _task(code="income_market_research", risk="medium"):
    agent = Agent.objects.create(
        code="economic-master-agent", name="Economic", mission="Internal evidence", active=True,
    )
    capability = AgentCapability.objects.create(
        code=code, name=code, risk_level=risk, active=True,
    )
    agent.capabilities.add(capability)
    return AgentTask.objects.create(
        agent=agent, action_type=code, capability_code=code,
        risk_snapshot=risk, input_data={}, status="queued",
    )


@pytest.mark.django_db
def test_economic_executor_never_invokes_factory_gateway_or_runner():
    task = _task()
    with patch("core.tool_gateway.ToolGateway.invoke", side_effect=AssertionError("factory gateway called")), patch(
        "core.worker_runner.WorkerRunner.run", side_effect=AssertionError("factory runner called")
    ):
        result = EconomicWorkerRunner(build_economic_master_gateway()).run(task.pk)
    assert result.status == "completed"
    assert result.output_data["verified_effect"] is True
    assert result.output_data["evidence"]["kind"] == "database_measurement"
    assert "verified_revenue" not in result.output_data
    assert result.cost == 0


@pytest.mark.django_db
def test_economic_executor_rejects_revoked_capability_without_claim():
    task = _task()
    task.agent.capabilities.clear()
    with pytest.raises(ValueError):
        EconomicWorkerRunner(build_economic_master_gateway()).run(task.pk)
    task.refresh_from_db()
    assert task.status == "queued" and task.attempt_count == 0


@pytest.mark.django_db
def test_economic_executor_refuses_factory_task_without_consuming_attempt():
    agent = Agent.objects.create(
        code="moj_1ro_1", name="Factory", mission="Private factory", active=True,
    )
    capability = AgentCapability.objects.create(
        code="income_market_research", name="Dummy", risk_level="medium", active=True,
    )
    agent.capabilities.add(capability)
    task = AgentTask.objects.create(
        agent=agent, action_type="income_market_research", capability_code="income_market_research",
        risk_snapshot="medium", input_data={}, status="queued",
    )
    with pytest.raises(EconomicExecutionError, match="not eligible"):
        EconomicWorkerRunner(build_economic_master_gateway()).run(task.pk)
    task.refresh_from_db()
    assert task.status == "queued" and task.attempt_count == 0


@pytest.mark.django_db
def test_economic_executor_rejects_tool_risk_higher_than_task_snapshot():
    task = _task(risk="low")
    with pytest.raises(EconomicExecutionError, match="risk exceeds"):
        EconomicWorkerRunner(build_economic_master_gateway()).run(task.pk)
    task.refresh_from_db()
    assert task.status == "queued" and task.attempt_count == 1


@pytest.mark.django_db
def test_economic_executor_rejects_evidence_free_fake_completion():
    task = _task()
    gateway = build_economic_master_gateway()
    # The internal registry is private and deliberately not a user-controlled API.
    gateway._tools["income_market_research"] = (
        "medium", lambda _: {"verified_effect": True, "action_performed": "claimed"},
    )
    with pytest.raises(EconomicExecutionError, match="concrete internal evidence"):
        EconomicWorkerRunner(gateway).run(task.pk)
    task.refresh_from_db()
    assert task.status == "queued"
    assert task.attempt_count == 1


@pytest.mark.django_db
def test_economic_executor_rejects_nonzero_cost_and_rolls_back_handler_writes():
    task = _task()
    gateway = build_economic_master_gateway()

    def forbidden_cost(_):
        Agent.objects.filter(pk=task.agent_id).update(name="SHOULD_ROLL_BACK")
        return {"__cost": "1", "verified_effect": True,
                "action_performed": "wrote", "evidence": {"kind": "db"}}

    gateway._tools["income_market_research"] = ("medium", forbidden_cost)
    with pytest.raises(EconomicExecutionError, match="financial cost"):
        EconomicWorkerRunner(gateway).run(task.pk)
    task.agent.refresh_from_db()
    assert task.agent.name == "Economic"


def test_factory_gateway_factory_tools_remain_untouched():
    assert {"factory_native_review", "factory_f41_private_build"}.issubset(
        build_economic_gateway().describe()
    )
    assert not {"factory_native_review", "factory_f41_private_build"}.intersection(
        build_economic_master_gateway().describe()
    )

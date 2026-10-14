import pytest
from django.core.management import call_command

from core.models import AgentTask, Robot


@pytest.mark.django_db
def test_worker_executes_first_economic_task_with_verified_evidence():
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    call_command("run_economic_worker")

    task = AgentTask.objects.get(capability_code="income_market_research")
    assert task.status == "completed"
    assert task.robot_id
    assert task.robot.connector == task.capability_code
    assert task.output_data["verified_effect"] is True
    assert task.output_data["action_performed"]
    assert task.output_data["evidence"]["kind"] == "database_measurement"
    assert Robot.objects.filter(agent=task.agent, deployment_status="sandbox").count() == 7


@pytest.mark.django_db
def test_cycle_advances_only_after_verified_completion():
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    call_command("run_economic_worker")
    call_command("online_income_cycle")

    tasks = list(AgentTask.objects.order_by("created_at"))
    assert len(tasks) == 2
    assert tasks[0].capability_code == "income_market_research"
    assert tasks[0].status == "completed"
    assert tasks[1].capability_code == "income_opportunity_score"
    assert tasks[1].robot.connector == tasks[1].capability_code
    assert tasks[1].status == "queued"


@pytest.mark.django_db
def test_seed_preserves_explicit_robot_pause():
    call_command("seed_online_income_agents")
    robot = Robot.objects.get(code="income-market-research-robot")
    robot.deployment_status = "paused"
    robot.save(update_fields=["deployment_status", "updated_at"])

    call_command("seed_online_income_agents")

    robot.refresh_from_db()
    assert robot.deployment_status == "paused"

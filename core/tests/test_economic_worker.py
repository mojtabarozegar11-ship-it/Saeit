import pytest
from django.core.management import call_command

from core.models import AgentTask


@pytest.mark.django_db
def test_worker_executes_first_self_improvement_task_with_verified_evidence(monkeypatch):
    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    call_command("run_economic_worker")

    task = AgentTask.objects.get(capability_code="master_self_improvement")
    assert task.status == "completed"
    assert task.output_data["verified_effect"] is True
    assert task.output_data["action_performed"]
    assert task.output_data["evidence"]["kind"] == "private_self_upgrade_dossier"
    assert task.output_data["production_promotion"] is False


@pytest.mark.django_db
def test_cycle_advances_from_self_improvement_to_verified_market_research(monkeypatch):
    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    call_command("run_economic_worker")
    call_command("online_income_cycle")

    tasks = list(AgentTask.objects.order_by("created_at"))
    assert len(tasks) == 2
    assert tasks[0].capability_code == "master_self_improvement"
    assert tasks[0].status == "completed"
    assert tasks[1].capability_code == "income_market_research"
    assert tasks[1].status == "queued"

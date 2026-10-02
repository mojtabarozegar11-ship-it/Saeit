import pytest

from core.agent_registry import AgentRegistry
from core.models import Agent, AgentCapability, AgentTask
from core.task_runtime import TaskExecutionError, TaskRuntime
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_online_income_agents_is_idempotent_and_single_agent():
    call_command("seed_online_income_agents")
    call_command("seed_online_income_agents")
    master = Agent.objects.get(code="economic-master-agent")
    assert master.active is True
    assert Agent.objects.filter(code__startswith="income-", active=True).count() == 0
    assert AgentCapability.objects.filter(code__startswith="income_").count() == 7
    assert master.capabilities.filter(code__startswith="income_", active=True).count() == 7


@pytest.mark.django_db
def test_registry_resolves_income_capability_to_master():
    call_command("seed_online_income_agents")
    agent = AgentRegistry().resolve("income_market_research")
    assert agent is not None
    assert agent.code == "economic-master-agent"


@pytest.mark.django_db
def test_income_cycle_dry_run_does_not_create_tasks():
    call_command("seed_online_income_agents")
    before = AgentTask.objects.count()
    call_command("online_income_cycle", "--dry-run")
    assert AgentTask.objects.count() == before


@pytest.mark.django_db
def test_income_cycle_queues_exactly_one_concrete_task():
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    tasks = AgentTask.objects.filter(capability_code__startswith="income_")
    assert tasks.count() == 1
    task = tasks.get()
    assert task.agent.code == "economic-master-agent"
    assert task.input_data["execution_contract"]["must_execute_not_just_report"] is True


@pytest.mark.django_db
def test_income_cycle_does_not_stack_work_while_prior_task_unfinished():
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    call_command("online_income_cycle")
    assert AgentTask.objects.filter(capability_code__startswith="income_").count() == 1


@pytest.mark.django_db
def test_economic_task_cannot_fake_completion_without_effect_evidence():
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    task = AgentTask.objects.get(capability_code="income_market_research")
    claimed = TaskRuntime().claim(task.pk)
    with pytest.raises(TaskExecutionError, match="verified_effect"):
        TaskRuntime().complete(
            task.pk,
            {"action_performed": "report only"},
            execution_id=claimed.execution_id,
        )

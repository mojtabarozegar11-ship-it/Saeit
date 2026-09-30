import pytest

from core.agent_registry import AgentRegistry
from core.models import Agent, AgentCapability
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_online_income_agents_is_idempotent():
    call_command("seed_online_income_agents")
    call_command("seed_online_income_agents")
    assert Agent.objects.filter(code__startswith="income-").count() == 4
    assert AgentCapability.objects.filter(code__startswith="income_").count() == 7


@pytest.mark.django_db
def test_registry_resolves_income_capability():
    call_command("seed_online_income_agents")
    agent = AgentRegistry().resolve("income_market_research")
    assert agent is not None
    assert agent.active is True
    assert agent.capabilities.filter(code="income_market_research", active=True).exists()


@pytest.mark.django_db
def test_income_cycle_dry_run_does_not_create_tasks():
    from core.models import AgentTask
    call_command("seed_online_income_agents")
    before = AgentTask.objects.count()
    call_command("online_income_cycle", "--dry-run")
    assert AgentTask.objects.count() == before


@pytest.mark.django_db
def test_income_cycle_queues_full_pipeline():
    from core.models import AgentTask
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    assert AgentTask.objects.filter(capability_code__startswith="income_").count() == 7
    assert not AgentTask.objects.filter(input_data__guardrails=[]).exists()

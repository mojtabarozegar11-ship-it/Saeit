import pytest
from django.core.management.base import CommandError

from core.canonical_bot_identity import CANONICAL_BOT_CODE, RUNTIME_CODES
from core.agent_registry import AgentRegistry
from core.management.commands.seed_online_income_agents import CAPABILITIES
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
    expected_income_codes = {
        code for code, *_ in CAPABILITIES if code.startswith("income_")
    }
    # The allowlist is authoritative; a new safe master module must not be
    # mistaken for a second independent bot or an unregistered capability.
    assert expected_income_codes
    assert set(AgentCapability.objects.filter(
        code__startswith="income_",
    ).values_list("code", flat=True)) == expected_income_codes
    assert set(master.capabilities.filter(
        code__startswith="income_", active=True,
    ).values_list("code", flat=True)) == expected_income_codes
    assert "income_mojtrade_research_review" in expected_income_codes
    assert list(Agent.objects.filter(
        capabilities__code="income_mojtrade_research_review"
    ).values_list("code", flat=True)) == ["economic-master-agent"]


@pytest.mark.django_db
def test_seeding_master_preserves_live_specialist_with_pending_task():
    specialist = Agent.objects.create(
        code="income-independent-specialist", name="Existing specialist",
        mission="Preserve useful independent task", active=True,
    )
    task = AgentTask.objects.create(
        agent=specialist, action_type="independent_delivery", status="queued"
    )
    call_command("seed_online_income_agents")
    specialist.refresh_from_db()
    task.refresh_from_db()
    assert specialist.active is True
    assert task.status == "queued"


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
    tasks = AgentTask.objects.filter(capability_code="master_self_improvement")
    assert tasks.count() == 1
    task = tasks.get()
    assert task.agent.code == "economic-master-agent"
    assert task.input_data["execution_contract"]["must_execute_not_just_report"] is True


@pytest.mark.django_db
def test_income_cycle_does_not_stack_work_while_prior_task_unfinished():
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    call_command("online_income_cycle")
    assert AgentTask.objects.filter(capability_code="master_self_improvement").count() == 1


@pytest.mark.django_db
def test_economic_task_cannot_fake_completion_without_effect_evidence():
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    task = AgentTask.objects.get(capability_code="master_self_improvement")
    claimed = TaskRuntime().claim(task.pk)
    with pytest.raises(TaskExecutionError, match="verified_effect"):
        TaskRuntime().complete(
            task.pk,
            {"action_performed": "report only"},
            execution_id=claimed.execution_id,
        )


@pytest.mark.django_db
def test_seed_never_reactivates_legacy_after_canonical_handoff():
    """Preserve task history and require one active master on repeat seeding."""
    Agent.objects.filter(code__in=RUNTIME_CODES).delete()
    legacy = Agent.objects.create(
        code="economic-master-agent", name="Old master", mission="historical",
        active=False,
    )
    old_task = AgentTask.objects.create(
        agent=legacy, action_type="income_market_research", status="completed",
    )
    canonical = Agent.objects.create(
        code=CANONICAL_BOT_CODE, name="Mojtaba.bot.ai",
        mission="single master", active=True,
    )
    call_command("seed_online_income_agents")
    call_command("seed_online_income_agents")
    legacy.refresh_from_db()
    canonical.refresh_from_db()
    old_task.refresh_from_db()
    assert legacy.active is False
    assert canonical.active is True
    assert old_task.agent_id == legacy.pk
    assert Agent.objects.filter(code__in=RUNTIME_CODES, active=True).count() == 1
    assert canonical.capabilities.filter(code="income_mojtrade_forward_audit", active=True).exists()
    assert not legacy.capabilities.filter(code="income_mojtrade_forward_audit", active=True).exists()


@pytest.mark.django_db
def test_seed_uses_existing_canonical_without_creating_legacy():
    Agent.objects.filter(code__in=RUNTIME_CODES).delete()
    canonical = Agent.objects.create(
        code=CANONICAL_BOT_CODE, name="Mojtaba.bot.ai", mission="single", active=True,
    )
    call_command("seed_online_income_agents")
    assert Agent.objects.filter(code="economic-master-agent").count() == 0
    canonical.refresh_from_db()
    assert canonical.active is True
    assert canonical.capabilities.filter(code="master_self_improvement", active=True).exists()


@pytest.mark.django_db
def test_seed_rejects_two_active_runtimes_without_touching_capabilities():
    Agent.objects.filter(code__in=RUNTIME_CODES).delete()
    legacy = Agent.objects.create(
        code="economic-master-agent", name="Old", mission="legacy", active=True,
    )
    canonical = Agent.objects.create(
        code=CANONICAL_BOT_CODE, name="Current", mission="canonical", active=True,
    )
    before = AgentCapability.objects.count()
    with pytest.raises(CommandError, match="MASTER_SEED_MULTIPLE_ACTIVE_RUNTIME_IDENTITIES"):
        call_command("seed_online_income_agents")
    assert AgentCapability.objects.count() == before
    legacy.refresh_from_db()
    canonical.refresh_from_db()
    assert legacy.active and canonical.active
    assert legacy.name == "Old"
    assert canonical.name == "Current"


@pytest.mark.django_db
def test_seed_refuses_to_restart_intentionally_deactivated_master():
    Agent.objects.filter(code__in=RUNTIME_CODES).delete()
    disabled = Agent.objects.create(
        code="economic-master-agent", name="Paused", mission="operator disabled",
        active=False,
    )
    before = AgentCapability.objects.count()
    with pytest.raises(CommandError, match="MASTER_SEED_REFUSES_INACTIVE_RUNTIME_REACTIVATION"):
        call_command("seed_online_income_agents")
    disabled.refresh_from_db()
    assert disabled.active is False
    assert AgentCapability.objects.count() == before


@pytest.mark.django_db
def test_seed_keeps_active_legacy_during_pending_canonical_handoff():
    """A preprovisioned but inactive canonical row is not a handoff instruction."""
    Agent.objects.filter(code__in=RUNTIME_CODES).delete()
    old = Agent.objects.create(
        code="economic-master-agent", name="Old", mission="existing", active=True,
    )
    new = Agent.objects.create(
        code=CANONICAL_BOT_CODE, name="Future", mission="pending", active=False,
    )
    call_command("seed_online_income_agents")
    old.refresh_from_db()
    new.refresh_from_db()
    assert old.active is True and new.active is False
    assert old.capabilities.filter(code="income_market_research", active=True).exists()
    assert not new.capabilities.filter(code="income_market_research", active=True).exists()


@pytest.mark.django_db
def test_seed_refuses_deactivated_canonical_and_legacy_after_handoff():
    Agent.objects.filter(code__in=RUNTIME_CODES).delete()
    legacy = Agent.objects.create(
        code="economic-master-agent", name="Old", mission="historical", active=False,
    )
    canonical = Agent.objects.create(
        code=CANONICAL_BOT_CODE, name="Disabled", mission="paused", active=False,
    )
    with pytest.raises(CommandError, match="MASTER_SEED_REFUSES_INACTIVE_RUNTIME_REACTIVATION"):
        call_command("seed_online_income_agents")
    assert Agent.objects.filter(code__in=RUNTIME_CODES, active=True).count() == 0
    assert canonical.pk and legacy.pk

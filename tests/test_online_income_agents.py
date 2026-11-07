import pytest

from core.agent_registry import AgentRegistry
from core.models import Agent, AgentCapability, AgentTask, CompanyInquiry
from core.task_runtime import TaskExecutionError, TaskRuntime
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_online_income_agents_is_idempotent_and_single_agent():
    call_command("seed_online_income_agents")
    call_command("seed_online_income_agents")
    master = Agent.objects.get(code="economic-master-agent")
    assert master.active is True
    assert Agent.objects.filter(code__startswith="income-", active=True).count() == 0
    assert AgentCapability.objects.filter(code__startswith="income_").count() == 8
    assert master.capabilities.filter(code__startswith="income_", active=True).count() == 8


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
def test_reseeding_never_reactivates_revoked_master_grants_or_agent():
    call_command("seed_online_income_agents", verbosity=0)
    master = Agent.objects.get(code="economic-master-agent")
    revoked = AgentCapability.objects.get(code="income_market_research")
    revoked.active = False
    revoked.risk_level = "high"
    revoked.save(update_fields=["active", "risk_level"])
    master.capabilities.remove(AgentCapability.objects.get(code="income_offer_design"))
    master.active = False
    master.save(update_fields=["active"])

    call_command("seed_online_income_agents", verbosity=0)
    master.refresh_from_db()
    revoked.refresh_from_db()
    assert master.active is False
    assert revoked.active is False
    assert revoked.risk_level == "high"
    assert not master.capabilities.filter(code="income_offer_design").exists()


@pytest.mark.django_db
def test_reseeding_does_not_overwrite_independent_factory_permissions():
    call_command("seed_online_income_agents", verbosity=0)
    factory = Agent.objects.get(code="moj_1ro_1")
    factory.capabilities.remove(AgentCapability.objects.get(code="factory_native_review"))
    factory.active = False
    factory.save(update_fields=["active"])

    call_command("seed_online_income_agents", verbosity=0)
    factory.refresh_from_db()
    assert factory.active is False
    assert not factory.capabilities.filter(code="factory_native_review").exists()


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
def test_real_inbound_inquiry_routes_to_private_review_once_without_contact():
    call_command("seed_online_income_agents", verbosity=0)
    inquiry = CompanyInquiry.objects.create(
        kind="commercial", name="Private Example", email="private@example.invalid",
        subject="Agricultural consulting", message="Please provide a proposal",
    )
    call_command("online_income_cycle", verbosity=0)
    task = AgentTask.objects.get(action_type="income_inbound_lead_review")
    assert task.input_data["inquiry_id"] == inquiry.pk
    assert task.status == "queued"

    call_command("run_economic_worker", verbosity=0)
    task.refresh_from_db()
    inquiry.refresh_from_db()
    assert task.status == "completed"
    assert inquiry.status == "reviewing"
    assert inquiry.internal_note.count(f"[economic-master:inbound-review:{inquiry.pk}]") == 1
    assert task.output_data["external_contact_performed"] is False
    assert task.output_data["customer_demand_independently_verified"] is False
    assert task.output_data["revenue_not_assessed"] is True
    assert "private@example.invalid" not in str(task.output_data)
    assert "Private Example" not in str(task.output_data)
    assert "Please provide a proposal" not in str(task.output_data)

    call_command("online_income_cycle", verbosity=0)
    assert AgentTask.objects.filter(action_type="income_inbound_lead_review").count() == 1
    assert AgentTask.objects.filter(action_type="master_self_improvement", status="queued").count() == 1


@pytest.mark.django_db
def test_closed_or_media_inquiry_never_spawns_commercial_triage():
    call_command("seed_online_income_agents", verbosity=0)
    CompanyInquiry.objects.create(
        kind="commercial", name="Closed", email="closed@example.invalid",
        subject="Old", message="Closed request", status="closed",
    )
    CompanyInquiry.objects.create(
        kind="media", name="Reporter", email="media@example.invalid",
        subject="Media", message="News media request", status="new",
    )
    call_command("online_income_cycle", verbosity=0)
    assert not AgentTask.objects.filter(action_type="income_inbound_lead_review").exists()
    assert AgentTask.objects.filter(action_type="master_self_improvement", status="queued").count() == 1


@pytest.mark.django_db
def test_legacy_inbound_task_without_source_id_does_not_hide_new_customer_inquiry():
    call_command("seed_online_income_agents", verbosity=0)
    master = Agent.objects.get(code="economic-master-agent")
    AgentTask.objects.create(
        agent=master, action_type="income_inbound_lead_review",
        capability_code="income_inbound_lead_review", status="failed", input_data={},
    )
    inquiry = CompanyInquiry.objects.create(
        kind="project", name="Customer", email="customer@example.invalid",
        subject="Service", message="I need a quotation",
    )
    call_command("online_income_cycle", verbosity=0)
    current = AgentTask.objects.get(action_type="income_inbound_lead_review", status="queued")
    assert current.input_data["inquiry_id"] == inquiry.pk


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

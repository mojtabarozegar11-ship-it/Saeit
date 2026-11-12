"""One bot identity across economic/factory lanes, with fail-closed migration."""

from io import StringIO
import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from core.approval import ApprovalService
from core.models import Agent, AgentTask, AuditLog, ApprovalRequest
from core.task_runtime import TaskExecutionError, TaskRuntime
from core.unified_bot_identity import BOT_CODE, BOT_NAME, LEGACY_EXECUTOR_CODES, module_for_capability


def approved_executor_handoff(old):
    """Synthetic DB-only fixture: never production proof of stopped schedulers."""
    owner = get_user_model().objects.create_user(username=f"merge-owner-{old.pk}")
    receipt = AuditLog.objects.create(
        actor_type="owner", actor_id=str(owner.pk),
        action="single_bot_live_handoff_verified",
        target_type="Agent", target_id=str(old.pk),
        before_state={"legacy_code": old.code},
        after_state={
            "legacy_code": old.code,
            "canonical_bot_code": BOT_CODE,
            "canonical_successor_runtime_verified": True,
            "external_legacy_schedulers_stopped": True,
            "all_pending_tasks_reconciled": True,
            "historical_data_preserved": True,
            "rollback_ready": True,
            "live_inventory_receipt_id": f"fixture-inventory-{old.pk}",
            "canonical_successor_receipt_id": f"fixture-successor-{old.pk}",
        },
        trace_id=f"fixture-merge-handoff-{old.pk}",
    )
    request = ApprovalRequest.objects.create(
        requested_by=owner, status="approved",
        action_type="merge_legacy_executor", target_type="Agent",
        target_id=str(old.pk), reason="Synthetic approved handoff fixture", risk="high",
    )
    grant = ApprovalService().issue_grant(request.pk, owner.pk, {
        "action": "merge_legacy_executor",
        "agent_code": old.code,
        "canonical_bot_code": BOT_CODE,
        "live_handoff_receipt": receipt.trace_id,
    })
    return receipt, grant


def seed(*, merge=False):
    if not merge:
        call_command("seed_online_income_agents", stdout=StringIO())
        return
    # Two separate one-agent operations, never a bulk owner-approval bypass.
    for old in Agent.objects.filter(
        code__in=LEGACY_EXECUTOR_CODES, active=True
    ).order_by("pk"):
        _, grant = approved_executor_handoff(old)
        call_command(
            "seed_online_income_agents", apply_legacy_merge=True,
            legacy_agent_code=old.code, approval_grant_id=grant.pk,
            stdout=StringIO(),
        )


@pytest.mark.django_db
def test_one_economic_and_factory_bot_is_seeded_with_bounded_permissions():
    seed()
    owner = Agent.objects.get(code=BOT_CODE)
    assert owner.active and owner.name == BOT_NAME
    assert {"income_market_research", "factory_native_review", "factory_f41_private_build"}.issubset(
        set(owner.capabilities.values_list("code", flat=True))
    )
    assert {"research-write-review", "content-editorial-draft"}.issubset(
        set(owner.capabilities.values_list("code", flat=True))
    )
    assert module_for_capability("research-write-review") == "knowledge_library"
    assert module_for_capability("content-editorial-draft") == "content_editorial"
    assert not owner.capabilities.filter(code__in=["trade", "payment", "deploy", "withdraw"]).exists()
    assert module_for_capability("factory_native_review") == "private_factory"
    assert module_for_capability("income_revenue_verify") == "economic_operations"
    assert module_for_capability("external_unknown") == "unmapped_requires_adapter_review"


@pytest.mark.django_db
def test_legacy_executors_merge_but_preserve_tasks_ids_and_audit_once():
    economic = Agent.objects.create(code="economic-master-agent", name="old", mission="old", active=True)
    factory = Agent.objects.create(code="moj_1ro_1", name="old", mission="old", active=True)
    economic_task = AgentTask.objects.create(
        agent=economic, action_type="income_market_research",
        capability_code="income_market_research", status="completed",
        output_data={"verified_effect": True},
    )
    factory_task = AgentTask.objects.create(
        agent=factory, action_type="factory_native_review",
        capability_code="factory_native_review", status="queued", risk_snapshot="low",
    )

    seed(merge=True)
    owner = Agent.objects.get(code=BOT_CODE)
    economic.refresh_from_db()
    factory.refresh_from_db()
    economic_task.refresh_from_db()
    factory_task.refresh_from_db()
    assert not economic.active and not factory.active
    assert economic_task.agent_id == economic.pk  # completed work keeps its historical owner
    assert factory_task.agent_id == owner.pk  # only unstarted work is reassigned
    assert economic_task.status == "completed"
    assert factory_task.status == "queued"
    assert Agent.objects.filter(code__in=("economic-master-agent", "moj_1ro_1")).count() == 2
    assert AuditLog.objects.filter(action="internal_executor_merged").count() == 2
    history_receipt = AuditLog.objects.get(action="internal_executor_merged", target_id=str(economic.pk))
    assert history_receipt.after_state["terminal_tasks_retained"] == 1
    assert history_receipt.after_state["queued_tasks_reassigned"] == 0
    assert history_receipt.after_state["historical_task_ownership_preserved"] is True

    seed()
    assert AuditLog.objects.filter(action="internal_executor_merged").count() == 2
    assert AgentTask.objects.filter(pk__in=(economic_task.pk, factory_task.pk)).count() == 2


@pytest.mark.django_db
def test_legacy_merge_requires_explicit_apply_flag():
    legacy = Agent.objects.create(
        code="moj_1ro_1", name="Old factory", mission="factory", active=True,
    )
    with pytest.raises(CommandError, match="REQUIRES_EXPLICIT_APPLY"):
        seed()
    legacy.refresh_from_db()
    assert legacy.active
    assert not Agent.objects.filter(code=BOT_CODE).exists()


@pytest.mark.django_db
def test_migration_of_running_legacy_job_is_blocked_without_partial_changes():
    old = Agent.objects.create(code="moj_1ro_1", name="old", mission="old", active=True)
    job = AgentTask.objects.create(
        agent=old, action_type="factory_native_review",
        capability_code="factory_native_review", status="running", execution_id="existing-worker",
    )
    with pytest.raises(CommandError, match="MIGRATION_BLOCKED_RUNNING_TASK"):
        seed(merge=True)
    assert not Agent.objects.filter(code=BOT_CODE).exists()
    job.refresh_from_db()
    assert job.agent_id == old.pk and job.status == "running"
    assert not AuditLog.objects.filter(action="internal_executor_merged").exists()


@pytest.mark.django_db
def test_unmapped_pending_legacy_job_blocks_atomic_migration():
    old = Agent.objects.create(code="economic-master-agent", name="old", mission="old", active=True)
    task = AgentTask.objects.create(
        agent=old, action_type="unknown_live_integration",
        capability_code="unknown_live_integration", status="queued",
    )
    with pytest.raises(CommandError, match="UNMAPPED_LEGACY_TASK"):
        seed(merge=True)
    assert not Agent.objects.filter(code=BOT_CODE).exists()
    task.refresh_from_db()
    assert task.agent_id == old.pk and task.status == "queued"


@pytest.mark.django_db
def test_single_bot_serialize_across_economic_and_factory_tasks():
    seed()
    owner = Agent.objects.get(code=BOT_CODE)
    economic = AgentTask.objects.create(
        agent=owner, action_type="income_market_research",
        capability_code="income_market_research", risk_snapshot="low", status="queued",
    )
    factory = AgentTask.objects.create(
        agent=owner, action_type="factory_native_review",
        capability_code="factory_native_review", risk_snapshot="low", status="queued",
    )
    claimed = TaskRuntime().claim(economic.pk)
    with pytest.raises(TaskExecutionError, match="already has a running task"):
        TaskRuntime().claim(factory.pk)
    TaskRuntime().complete(economic.pk, {
        "verified_effect": True, "action_performed": "internal inventory",
        "evidence": {"kind": "inventory", "value": "record"},
    }, execution_id=claimed.execution_id)
    assert TaskRuntime().claim(factory.pk).status == "running"


@pytest.mark.django_db
def test_fleet_audit_distinguishes_one_owner_from_unmerged_live_roles():
    seed()
    Agent.objects.update_or_create(
        code="newsletter-world-watch",
        defaults={"name": "old", "mission": "world", "active": True},
    )
    out = StringIO()
    call_command("audit_agent_fleet", stdout=out)
    data = json.loads(out.getvalue())
    assert data["canonical_bot"] == {"code": BOT_CODE, "name": BOT_NAME}
    assert data["full_consolidation_attested"] is False
    assert data["summary"]["noncanonical_active_agent_rows"] >= 1
    rows = {row["code"]: row for row in data["agents"]}
    assert rows[BOT_CODE]["consolidation_state"] == "single_bot_owner"
    assert rows["newsletter-world-watch"]["consolidation_state"] == "internal_role_dependency_review_required"


@pytest.mark.django_db
def test_blocked_factory_review_does_not_permanently_freeze_economic_planning():
    seed()
    owner = Agent.objects.get(code=BOT_CODE)
    factory = AgentTask.objects.create(
        agent=owner, action_type="factory_native_review",
        capability_code="factory_native_review", status="blocked",
        output_data={"requires_review": True},
    )
    out = StringIO()
    call_command("online_income_cycle", stdout=out)
    assert "BRAIN_DECISION" in out.getvalue()
    assert AgentTask.objects.filter(agent=owner, capability_code="master_self_improvement", status="queued").count() == 1
    factory.refresh_from_db()
    assert factory.status == "blocked"


@pytest.mark.django_db
def test_factory_queue_is_not_misreported_as_unknown_economic_capability():
    seed()
    owner = Agent.objects.get(code=BOT_CODE)
    AgentTask.objects.create(
        agent=owner, action_type="factory_f41_private_build",
        capability_code="factory_f41_private_build", status="queued",
    )
    out = StringIO()
    call_command("run_economic_worker", stdout=out)
    assert "IDLE: no queued economic task." in out.getvalue()
    assert "BLOCKED_UNSUPPORTED" not in out.getvalue()


@pytest.mark.django_db
def test_knowledge_task_under_canonical_owner_is_not_executed_as_economic_work():
    seed()
    owner = Agent.objects.get(code=BOT_CODE)
    knowledge = AgentTask.objects.create(
        agent=owner, action_type="knowledge_content_generation",
        capability_code="research-write-review", risk_snapshot="high",
        status="queued", input_data={"approval_required": True, "paid_model": True},
    )
    output = StringIO()
    call_command("run_economic_worker", stdout=output)
    assert "IDLE: no queued economic task." in output.getvalue()
    assert "BLOCKED_UNSUPPORTED" not in output.getvalue()
    knowledge.refresh_from_db()
    assert knowledge.status == "queued"
    assert knowledge.attempt_count == 0


@pytest.mark.django_db
def test_mismatched_editorial_task_is_not_hidden_from_unknown_work_review():
    seed()
    owner = Agent.objects.get(code=BOT_CODE)
    bad = AgentTask.objects.create(
        agent=owner, action_type="unexpected_external_action",
        capability_code="research-write-review", status="queued",
    )
    output = StringIO()
    call_command("run_economic_worker", stdout=output)
    assert f"BLOCKED_UNSUPPORTED: task={bad.pk}" in output.getvalue()
    bad.refresh_from_db()
    assert bad.status == "queued"


@pytest.mark.django_db
def test_known_knowledge_queue_does_not_appear_as_economic_brain_continue():
    seed()
    owner = Agent.objects.get(code=BOT_CODE)
    job = AgentTask.objects.create(
        agent=owner, action_type="knowledge_content_generation",
        capability_code="research-write-review", status="queued",
    )
    output = StringIO()
    call_command("online_income_cycle", "--dry-run", stdout=output)
    assert f"BRAIN_CONTINUE task={job.pk}" not in output.getvalue()
    job.refresh_from_db()
    assert job.status == "queued"

@pytest.mark.django_db
def test_blocked_legacy_approval_task_blocks_merge_without_any_registry_changes():
    old = Agent.objects.create(code="economic-master-agent", name="old", mission="old", active=True)
    blocked = AgentTask.objects.create(
        agent=old, action_type="income_market_research",
        capability_code="income_market_research", status="blocked",
    )
    with pytest.raises(CommandError, match="UNRECONCILED_TASK"):
        seed(merge=True)
    blocked.refresh_from_db()
    old.refresh_from_db()
    assert blocked.agent_id == old.pk and blocked.status == "blocked"
    assert old.active
    assert not Agent.objects.filter(code=BOT_CODE).exists()
    assert not AuditLog.objects.filter(action="internal_executor_merged").exists()


@pytest.mark.django_db
def test_mismatched_queued_action_is_never_relabelled_as_supported_capability():
    old = Agent.objects.create(code="moj_1ro_1", name="old", mission="old", active=True)
    queued = AgentTask.objects.create(
        agent=old, action_type="unreviewed_external_write",
        capability_code="income_market_research", status="queued",
    )
    with pytest.raises(CommandError, match="MISMATCHED_LEGACY_TASK"):
        seed(merge=True)
    queued.refresh_from_db()
    assert queued.agent_id == old.pk and queued.status == "queued"
    assert not Agent.objects.filter(code=BOT_CODE).exists()


@pytest.mark.django_db
def test_failed_and_cancelled_legacy_receipts_remain_with_original_owner():
    old = Agent.objects.create(code="economic-master-agent", name="old", mission="old", active=True)
    terminal = [
        AgentTask.objects.create(
            agent=old, action_type="income_market_research",
            capability_code="income_market_research", status=status,
        ) for status in ("failed", "cancelled")
    ]
    seed(merge=True)
    canonical = Agent.objects.get(code=BOT_CODE)
    old.refresh_from_db()
    assert canonical.active and not old.active
    for task in terminal:
        task.refresh_from_db()
        assert task.agent_id == old.pk
    receipt = AuditLog.objects.get(action="internal_executor_merged", target_id=str(old.pk))
    assert receipt.after_state["terminal_tasks_retained"] == 2
    assert receipt.after_state["queued_tasks_reassigned"] == 0
    seed()  # historical terminal rows alone never force another migration
@pytest.mark.django_db
def test_plain_apply_flag_cannot_disable_legacy_executor():
    old = Agent.objects.create(code="moj_1ro_1", name="old", mission="factory", active=True)
    with pytest.raises(CommandError, match="EXACT_LEGACY_AGENT_AND_APPROVAL_REQUIRED"):
        call_command("seed_online_income_agents", apply_legacy_merge=True, stdout=StringIO())
    old.refresh_from_db()
    assert old.active
    assert not Agent.objects.filter(code=BOT_CODE).exists()


@pytest.mark.django_db
def test_approval_without_handoff_is_not_enough_to_retire_executor():
    old = Agent.objects.create(code="economic-master-agent", name="old", mission="economic", active=True)
    _, grant = approved_executor_handoff(old)
    AuditLog.objects.filter(action="single_bot_live_handoff_verified", target_id=str(old.pk)).delete()
    with pytest.raises(CommandError, match="LIVE_HANDOFF_RECEIPT_REQUIRED"):
        call_command(
            "seed_online_income_agents", apply_legacy_merge=True,
            legacy_agent_code=old.code, approval_grant_id=grant.pk,
            stdout=StringIO(),
        )
    old.refresh_from_db()
    grant.refresh_from_db()
    assert old.active and grant.used_at is None
    assert not Agent.objects.filter(code=BOT_CODE).exists()


@pytest.mark.django_db
def test_wrong_scope_grant_fails_atomically_without_legacy_retirement():
    old = Agent.objects.create(code="moj_1ro_1", name="old", mission="factory", active=True)
    _, grant = approved_executor_handoff(old)
    grant.scope["agent_code"] = "economic-master-agent"
    grant.save(update_fields=["scope"])
    with pytest.raises(CommandError, match="APPROVAL_GRANT_REJECTED"):
        call_command(
            "seed_online_income_agents", apply_legacy_merge=True,
            legacy_agent_code=old.code, approval_grant_id=grant.pk,
            stdout=StringIO(),
        )
    old.refresh_from_db()
    grant.refresh_from_db()
    assert old.active and grant.used_at is None
    assert not Agent.objects.filter(code=BOT_CODE).exists()


@pytest.mark.django_db
def test_one_executor_approval_cannot_retire_the_other():
    first = Agent.objects.create(code="economic-master-agent", name="economic", mission="old", active=True)
    second = Agent.objects.create(code="moj_1ro_1", name="factory", mission="old", active=True)
    _, first_grant = approved_executor_handoff(first)
    with pytest.raises(CommandError, match="EXACT_OWNER_APPROVAL_REQUIRED"):
        call_command(
            "seed_online_income_agents", apply_legacy_merge=True,
            legacy_agent_code=second.code, approval_grant_id=first_grant.pk,
            stdout=StringIO(),
        )
    first.refresh_from_db()
    second.refresh_from_db()
    first_grant.refresh_from_db()
    assert first.active and second.active and first_grant.used_at is None
    assert not Agent.objects.filter(code=BOT_CODE).exists()

    call_command(
        "seed_online_income_agents", apply_legacy_merge=True,
        legacy_agent_code=first.code, approval_grant_id=first_grant.pk,
        stdout=StringIO(),
    )
    first.refresh_from_db()
    second.refresh_from_db()
    first_grant.refresh_from_db()
    assert not first.active and second.active and first_grant.used_at is not None
    with pytest.raises(CommandError):
        call_command(
            "seed_online_income_agents", apply_legacy_merge=True,
            legacy_agent_code=first.code, approval_grant_id=first_grant.pk,
            stdout=StringIO(),
        )
    assert Agent.objects.get(pk=second.pk).active
    assert AuditLog.objects.filter(action="internal_executor_merged").count() == 1


@pytest.mark.django_db
def test_partial_live_receipt_is_not_retirement_authority():
    old = Agent.objects.create(code="economic-master-agent", name="old", mission="economic", active=True)
    receipt, grant = approved_executor_handoff(old)
    receipt.after_state["external_legacy_schedulers_stopped"] = False
    receipt.save(update_fields=["after_state"])
    with pytest.raises(CommandError, match="LIVE_HANDOFF_RECEIPT_REQUIRED"):
        call_command(
            "seed_online_income_agents", apply_legacy_merge=True,
            legacy_agent_code=old.code, approval_grant_id=grant.pk,
            stdout=StringIO(),
        )
    assert Agent.objects.get(pk=old.pk).active
    grant.refresh_from_db()
    assert grant.used_at is None

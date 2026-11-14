"""Targeted regression suite for the existing master bot's execute/replan path.

Fixtures never contact customers, providers, a broker or a production runtime.
"""
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.management.commands.autonomous_master_loop import (
    Command, REPLAN_PREREQUISITES, _failure_classification,
    registered_economic_tools,
)
from core.models import Agent, AgentCapability, AgentTask


def gateway(enabled=None):
    enabled = enabled or {"income_market_research": {"enabled": True}}
    return SimpleNamespace(describe=lambda: enabled)


@pytest.fixture
def bot(db):
    master = Agent.objects.create(
        code="economic-master-agent", name="Master",
        mission="Deliver verified commercial work", active=True
    )
    for code in ("income_market_research", "income_mvp_build", "income_offer_design"):
        cap = AgentCapability.objects.create(
            code=code, name=code, active=True, risk_level="low"
        )
        cap.agents.add(master)
    return master


def enqueue(master, code="income_market_research", status="queued"):
    return AgentTask.objects.create(
        agent=master, action_type=code, capability_code=code,
        risk_snapshot="low", status=status
    )


@pytest.mark.parametrize("bad", [None, [], "not a mapping", 1])
def test_invalid_gateway_registry_is_not_executable(bad):
    with pytest.raises(CommandError, match="registry is invalid"):
        registered_economic_tools(SimpleNamespace(describe=lambda: bad))


def test_only_explicitly_enabled_economic_tools_are_accepted():
    result = registered_economic_tools(gateway({
        "income_market_research": {"enabled": True},
        "income_offer_design": {"enabled": False},
        "income_mvp_build": {"enabled": 1},
        "transfer_funds": {"enabled": True},
        "arbitrary_command": {"enabled": True},
        "master_self_improvement": {"enabled": True},
        "income_fake": "enabled",
    }))
    assert result == {"income_market_research", "master_self_improvement"}


@pytest.mark.parametrize("limit", [0, -1, -10])
def test_master_rejects_nonpositive_step_budget(limit):
    with pytest.raises(CommandError, match="positive integer"):
        call_command("autonomous_master_loop", max_steps=limit)


@pytest.mark.django_db
def test_master_clamps_oversize_step_budget():
    output = StringIO()
    with patch("core.management.commands.autonomous_master_loop.build_economic_gateway",
               return_value=gateway()):
        call_command("autonomous_master_loop", max_steps=999, stdout=output)
    assert "AUTO_SERIAL_STEP_CAP requested=999 applied=20" in output.getvalue()


@pytest.mark.django_db
def test_idle_agent_does_not_fabricate_completed_task(bot):
    output = StringIO()
    with patch("core.management.commands.autonomous_master_loop.build_economic_gateway",
               return_value=gateway()):
        call_command("autonomous_master_loop", max_steps=1, stdout=output)
    assert AgentTask.objects.filter(agent=bot, status="completed").count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("variant,receipt,expected", [
    ("wrong_identity", {"pk": -1, "status": "completed",
                        "action_type": "income_market_research",
                        "output_data": {"verified_effect": True}},
     "AUTO_TASK_IDENTITY_MISMATCH_STOP"),
    ("failed_status", {"status": "failed", "action_type": "income_market_research",
                       "output_data": {"verified_effect": True}},
     "AUTO_INCOMPLETE_TASK_STOP"),
    ("bad_receipt", {"status": "completed", "action_type": "income_market_research",
                     "output_data": "not an object"},
     "AUTO_INVALID_RECEIPT_STOP"),
    ("wrong_action", {"status": "completed", "action_type": "income_offer_design",
                      "output_data": {"verified_effect": True}},
     "AUTO_TASK_ACTION_MISMATCH_STOP"),
    ("textual_true", {"status": "completed", "action_type": "income_market_research",
                      "output_data": {"verified_effect": "True"}},
     "AUTO_UNVERIFIED_STOP"),
    ("boolean_false", {"status": "completed", "action_type": "income_market_research",
                       "output_data": {"verified_effect": False}},
     "AUTO_UNVERIFIED_STOP"),
])
def test_non_verified_or_mismatched_worker_result_never_counts_as_success(
        bot, variant, receipt, expected):
    task = enqueue(bot)
    done = SimpleNamespace(
        pk=receipt.get("pk", task.pk),
        status=receipt["status"],
        action_type=receipt["action_type"],
        output_data=receipt["output_data"],
        refresh_from_db=lambda: None,
    )
    with patch("core.management.commands.autonomous_master_loop.build_economic_gateway",
               return_value=gateway()), patch(
        "core.management.commands.autonomous_master_loop.WorkerRunner"
    ) as runner:
        runner.return_value.run.return_value = done
        output = StringIO()
        call_command("autonomous_master_loop", max_steps=1, stdout=output)
    assert expected in output.getvalue()
    assert "revenue_not_assessed=true" not in output.getvalue() or (
        "internal_effect_verified=0" in output.getvalue()
    )


@pytest.mark.django_db
def test_successful_internal_task_is_not_called_cash_revenue(bot):
    task = enqueue(bot)
    done = SimpleNamespace(
        pk=task.pk, status="completed", action_type=task.action_type,
        output_data={"verified_effect": True, "action_performed": "private"},
        refresh_from_db=lambda: None,
    )
    with patch("core.management.commands.autonomous_master_loop.build_economic_gateway",
               return_value=gateway()), patch(
        "core.management.commands.autonomous_master_loop.WorkerRunner"
    ) as runner:
        runner.return_value.run.return_value = done
        out = StringIO()
        call_command("autonomous_master_loop", max_steps=1, stdout=out)
    assert "internal_effect_verified=1" in out.getvalue()
    assert "revenue_not_assessed=true" in out.getvalue()
    assert "verified_revenue=" not in out.getvalue()


@pytest.mark.django_db
def test_failed_tool_does_not_expose_raw_secret_or_create_spurious_work(bot):
    original = enqueue(bot)
    secret = "SECRET_CUSTOMER_TOKEN_SHOULD_NOT_APPEAR"
    with patch("core.management.commands.autonomous_master_loop.build_economic_gateway",
               return_value=gateway()), patch(
        "core.management.commands.autonomous_master_loop.WorkerRunner"
    ) as runner:
        runner.return_value.run.side_effect = RuntimeError(secret)
        out = StringIO()
        call_command("autonomous_master_loop", max_steps=1, stdout=out)
    assert secret not in out.getvalue()
    assert "reason_code=worker_execution" in out.getvalue()
    assert AgentTask.objects.filter(agent=bot).count() == 1
    original.refresh_from_db()
    assert original.status == "queued"


@pytest.mark.django_db
def test_unknown_queued_capability_is_reported_without_leaking_its_name(bot):
    unsafe_code = "income_external_secret_lookup"
    task = enqueue(bot, code=unsafe_code)
    out = StringIO()
    with patch("core.management.commands.autonomous_master_loop.build_economic_gateway",
               return_value=gateway()):
        call_command("autonomous_master_loop", max_steps=1, stdout=out)
    assert "AUTO_BLOCKED_UNSUPPORTED_TASK" in out.getvalue()
    assert f"task={task.pk}" in out.getvalue()
    assert unsafe_code not in out.getvalue()
    task.refresh_from_db()
    assert task.status == "queued"


@pytest.mark.django_db
def test_atomic_replan_creates_a_single_true_dependency(bot):
    old = enqueue(bot)
    state = Command._replan_task(old.pk, "income_mvp_build")
    assert state == "created"
    old.refresh_from_db()
    assert old.status == "cancelled"
    assert old.output_data["replan_reason_code"] == "dependency_missing"
    new = AgentTask.objects.get(agent=bot, capability_code="income_mvp_build")
    assert new.input_data["replanned_from"] == old.pk
    assert new.input_data["execution_contract"]["must_execute_not_just_report"] is True


@pytest.mark.django_db
def test_replan_respects_existing_prerequisite_queue_and_avoids_duplicate(bot):
    old = enqueue(bot)
    preexisting = enqueue(bot, code="income_mvp_build")
    assert Command._replan_task(old.pk, "income_mvp_build") == "existing_prerequisite"
    assert AgentTask.objects.filter(
        agent=bot, capability_code="income_mvp_build"
    ).count() == 1
    old.refresh_from_db()
    assert old.status == "cancelled"
    preexisting.refresh_from_db()
    assert preexisting.status == "queued"


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["running", "blocked", "completed", "failed", "cancelled"])
def test_replan_cannot_overwrite_other_task_lifecycle(bot, status):
    task = enqueue(bot, status=status)
    assert Command._replan_task(task.pk, "income_mvp_build") == "task_not_queued"
    task.refresh_from_db()
    assert task.status == status
    assert AgentTask.objects.count() == 1


@pytest.mark.django_db
def test_replan_inactive_agent_fails_closed(bot):
    task = enqueue(bot)
    bot.active = False
    bot.save(update_fields=["active"])
    assert Command._replan_task(task.pk, "income_mvp_build") == "inactive_agent"
    task.refresh_from_db()
    assert task.status == "queued"


@pytest.mark.django_db
def test_replan_unregistered_prerequisite_is_refused(bot):
    task = enqueue(bot)
    assert Command._replan_task(task.pk, "transfer_funds") == "unknown_prerequisite"
    task.refresh_from_db()
    assert task.status == "queued"
    assert AgentTask.objects.count() == 1


@pytest.mark.django_db
def test_replan_missing_enabled_capability_does_not_cancel_original(bot):
    task = enqueue(bot)
    bot.capabilities.remove(AgentCapability.objects.get(code="income_mvp_build"))
    assert Command._replan_task(task.pk, "income_mvp_build") == "missing_capability"
    task.refresh_from_db()
    assert task.status == "queued"


@pytest.mark.django_db
def test_failed_tool_prerequisite_recovery_is_end_to_end_redacted(bot):
    task = enqueue(bot)
    reason = "No built MVP exists SECRET_LEAD_PRIVATE_EMAIL"
    supported = gateway({
        "income_market_research": {"enabled": True},
        "income_mvp_build": {"enabled": True},
    })
    with patch("core.management.commands.autonomous_master_loop.build_economic_gateway",
               return_value=supported), patch(
        "core.management.commands.autonomous_master_loop.WorkerRunner"
    ) as runner:
        runner.return_value.run.side_effect = ValueError(reason)
        out = StringIO()
        call_command("autonomous_master_loop", max_steps=1, stdout=out)
    assert reason not in out.getvalue()
    assert "AUTO_REPLAN_STATE=created" in out.getvalue()
    task.refresh_from_db()
    assert task.status == "cancelled"
    assert AgentTask.objects.filter(
        agent=bot, capability_code="income_mvp_build", status="queued"
    ).count() == 1


def test_replan_allowlist_has_no_financial_or_external_actions():
    assert REPLAN_PREREQUISITES == {"income_mvp_build", "income_offer_design"}
    assert _failure_classification(ValueError("private password")) == "validation_or_policy"
    assert _failure_classification(RuntimeError("private password")) == "worker_execution"


@pytest.mark.django_db
def test_economic_worker_redacts_private_unsupported_capability(bot):
    secret_code = "income_private_buyer_token_DO_NOT_LOG"
    enqueue(bot, code=secret_code)
    with patch("core.management.commands.run_economic_worker.build_economic_gateway",
               return_value=gateway()), patch(
        "core.management.commands.run_economic_worker.WorkerRunner"
    ) as runner:
        out = StringIO()
        call_command("run_economic_worker", stdout=out)
    runner.assert_not_called()
    assert "BLOCKED_UNSUPPORTED" in out.getvalue()
    assert secret_code not in out.getvalue()


@pytest.mark.django_db
def test_economic_worker_redacts_raw_tool_failure_and_preserves_queue(bot):
    task = enqueue(bot)
    secret = "CUSTOMER_PRIVATE_PAYMENT_REFERENCE_SECRET"
    with patch("core.management.commands.run_economic_worker.build_economic_gateway",
               return_value=gateway()), patch(
        "core.management.commands.run_economic_worker.WorkerRunner"
    ) as runner:
        runner.return_value.run.side_effect = RuntimeError(secret)
        with pytest.raises(CommandError) as raised:
            call_command("run_economic_worker")
    assert secret not in str(raised.value)
    assert "worker_execution_error" in str(raised.value)
    assert raised.value.__suppress_context__ is True
    task.refresh_from_db()
    assert task.status == "queued"


@pytest.mark.django_db
@pytest.mark.parametrize("output,verified", [
    ({"verified_effect": "yes"}, "0"),
    ({"verified_effect": 1}, "0"),
    ({"verified_effect": True}, "1"),
    (None, "0"),
    ("raw string", "0"),
])
def test_economic_worker_receipt_effect_must_be_explicit_boolean(
        bot, output, verified):
    task = enqueue(bot)
    done = SimpleNamespace(pk=task.pk, status="completed", output_data=output)
    with patch("core.management.commands.run_economic_worker.build_economic_gateway",
               return_value=gateway()), patch(
        "core.management.commands.run_economic_worker.WorkerRunner"
    ) as runner:
        runner.return_value.run.return_value = done
        out = StringIO()
        call_command("run_economic_worker", stdout=out)
    assert f"internal_effect_verified={verified}" in out.getvalue()
    assert "revenue_not_assessed=true" in out.getvalue()


@pytest.mark.django_db
def test_stale_running_task_is_recovered_even_if_another_task_is_queued(bot):
    from datetime import timedelta
    from django.utils import timezone

    already_queued = enqueue(bot)
    orphan = enqueue(bot, code="income_offer_design", status="running")
    orphan.attempt_count = 1
    orphan.max_attempts = 3
    orphan.execution_id = "stale-execution-id"
    orphan.save(update_fields=["attempt_count", "max_attempts", "execution_id"])
    AgentTask.objects.filter(pk=orphan.pk).update(
        updated_at=timezone.now() - timedelta(hours=2)
    )
    out = StringIO()
    call_command("online_income_cycle", stale_after_seconds=900, stdout=out)
    orphan.refresh_from_db()
    already_queued.refresh_from_db()
    assert "BRAIN_RECOVERED" in out.getvalue()
    assert orphan.status == "queued"
    assert orphan.execution_id == ""
    assert already_queued.status == "queued"
    assert AgentTask.objects.filter(agent=bot).count() == 2


@pytest.mark.django_db
def test_active_running_task_is_never_ignored_due_to_other_queued_work(bot):
    queued = enqueue(bot)
    running = enqueue(bot, code="income_offer_design", status="running")
    running.attempt_count = 1
    running.execution_id = "live-execution-id"
    running.save(update_fields=["attempt_count", "execution_id"])
    out = StringIO()
    call_command("online_income_cycle", stale_after_seconds=900, stdout=out)
    assert "BRAIN_RUNNING" in out.getvalue()
    assert "BRAIN_CONTINUE" not in out.getvalue()
    running.refresh_from_db()
    queued.refresh_from_db()
    assert running.status == "running"
    assert running.execution_id == "live-execution-id"
    assert queued.status == "queued"


@pytest.mark.django_db
def test_dry_run_with_mixed_queue_never_recovers_or_writes(bot):
    from datetime import timedelta
    from django.utils import timezone

    queued = enqueue(bot)
    running = enqueue(bot, code="income_offer_design", status="running")
    running.execution_id = "old-but-owned"
    running.attempt_count = 1
    running.save(update_fields=["attempt_count", "execution_id"])
    AgentTask.objects.filter(pk=running.pk).update(
        updated_at=timezone.now() - timedelta(hours=3)
    )
    before = AgentTask.objects.count()
    out = StringIO()
    call_command("online_income_cycle", dry_run=True, stdout=out)
    running.refresh_from_db()
    queued.refresh_from_db()
    assert running.status == "running"
    assert running.execution_id == "old-but-owned"
    assert queued.status == "queued"
    assert AgentTask.objects.count() == before
    assert "BRAIN_RUNNING" in out.getvalue()

import json
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from core.models import Agent, AgentCapability, AgentTask, AuditLog


@pytest.mark.django_db
def test_fleet_audit_is_read_only_and_reports_known_executor_gaps():
    master = Agent.objects.create(
        code="economic-master-agent", name="Master", mission="Revenue", active=True,
    )
    AgentCapability.objects.create(
        code="income_market_research", name="Internal inventory", active=True,
    ).agents.add(master)
    AgentTask.objects.create(
        agent=master, action_type="income_market_research",
        capability_code="income_market_research", status="completed",
    )
    AgentTask.objects.create(
        agent=master, action_type="income_nonexistent_publish",
        capability_code="income_nonexistent_publish", status="queued",
    )
    AgentTask.objects.create(
        agent=master, action_type="income_market_research",
        capability_code="income_market_research", status="running",
    )
    AgentTask.objects.filter(status="running").update(
        updated_at=timezone.now() - timedelta(hours=2)
    )
    inactive = Agent.objects.create(
        code="disabled-specialist", name="Inactive", mission="Old", active=False,
    )
    AgentTask.objects.create(agent=inactive, action_type="unknown", status="queued")
    twin_a = Agent.objects.create(code="duplicate-a", name="A", mission="  Same  work ", active=True)
    twin_b = Agent.objects.create(code="duplicate-b", name="B", mission="same work", active=True)
    shared = AgentCapability.objects.create(code="shared_internal", name="Shared", active=True)
    shared.agents.add(twin_a, twin_b)
    before = (AgentTask.objects.count(), AuditLog.objects.count())

    output = StringIO()
    call_command("audit_agent_fleet", stdout=output)
    report = json.loads(output.getvalue())
    assert report["mode"] == "read_only"
    assert report["live_scheduler_attested"] is False
    assert report["verified_revenue_attested"] is False
    assert report["summary"]["unsupported_known_queue_tasks"] == 1
    assert report["summary"]["stale_running_tasks"] == 1
    assert report["summary"]["exact_duplicate_role_groups"] == 1
    rows = {row["code"]: row for row in report["agents"]}
    assert rows["economic-master-agent"]["known_registered_handlers"] == ["income_market_research"]
    assert "queued_task_not_supported_by_known_executor" in rows["economic-master-agent"]["findings"]
    assert "inactive_agent_has_pending_tasks" in rows["disabled-specialist"]["findings"]
    assert rows["duplicate-a"]["exact_role_duplicates"] == ["duplicate-b"]
    assert (AgentTask.objects.count(), AuditLog.objects.count()) == before


@pytest.mark.parametrize("kwargs", [
    {"days": 0}, {"days": 366}, {"stale_after": 0}, {"stale_after": 86401},
])
def test_fleet_audit_rejects_unbounded_options(kwargs):
    with pytest.raises(CommandError):
        call_command("audit_agent_fleet", **kwargs)


@pytest.mark.django_db
def test_fleet_audit_covers_canonical_master_registered_handlers_without_mutation():
    """Canonical handoff must not hide authorized capabilities."""
    master, _ = Agent.objects.update_or_create(
        code="mojtaba-bot-ai",
        defaults={"name": "Mojtaba.bot.ai", "mission": "Private canonical audit", "active": True},
    )
    capability, _ = AgentCapability.objects.update_or_create(
        code="income_market_research",
        defaults={"name": "Internal inventory", "active": True},
    )
    master.capabilities.clear()
    master.capabilities.add(capability)
    AgentTask.objects.filter(agent=master).delete()
    task = AgentTask.objects.create(
        agent=master, action_type="income_market_research",
        capability_code="income_market_research", status="queued",
    )
    counts = (AgentTask.objects.count(), AuditLog.objects.count())
    output = StringIO()
    call_command("audit_agent_fleet", stdout=output)
    report = json.loads(output.getvalue())
    row = next(x for x in report["agents"] if x["code"] == "mojtaba-bot-ai")
    assert row["handler_coverage"] == "partial_known_scope"
    assert "income_market_research" in row["known_registered_handlers"]
    assert row["tasks"]["queued_without_known_handler"] == 0
    task.refresh_from_db()
    assert task.status == "queued"
    assert (AgentTask.objects.count(), AuditLog.objects.count()) == counts


@pytest.mark.django_db
def test_fleet_audit_flags_unknown_canonical_master_tool_without_dispatch():
    """Unknown tools stay queued and explicitly identified for review."""
    master, _ = Agent.objects.update_or_create(
        code="mojtaba-bot-ai",
        defaults={"name": "Mojtaba.bot.ai", "mission": "Private canonical audit", "active": True},
    )
    master.capabilities.clear()
    AgentTask.objects.filter(agent=master).delete()
    task = AgentTask.objects.create(
        agent=master, action_type="income_unregistered_remote_trade",
        capability_code="income_unregistered_remote_trade", status="queued",
    )
    before = (AgentTask.objects.count(), task.attempt_count, AuditLog.objects.count())
    output = StringIO()
    call_command("audit_agent_fleet", stdout=output)
    report = json.loads(output.getvalue())
    row = next(x for x in report["agents"] if x["code"] == "mojtaba-bot-ai")
    assert row["tasks"]["queued_without_known_handler"] == 1
    assert "queued_task_not_supported_by_known_executor" in row["findings"]
    task.refresh_from_db()
    assert task.status == "queued"
    assert (AgentTask.objects.count(), task.attempt_count, AuditLog.objects.count()) == before


@pytest.mark.django_db
def test_handoff_audit_distinguishes_source_checks_from_live_cutover():
    from core.management.commands.seed_online_income_agents import ASSIGNMENTS
    from core.canonical_bot_identity import RUNTIME_CODES

    Agent.objects.filter(code__in=RUNTIME_CODES).delete()
    Agent.objects.create(
        code="mojtaba-bot-ai", name="Mojtaba.bot.ai",
        mission="canonical", active=True,
    )
    call_command("seed_online_income_agents")
    before = (AgentTask.objects.count(), AuditLog.objects.count())
    out = StringIO()
    call_command("audit_agent_fleet", stdout=out)
    report = json.loads(out.getvalue())
    handoff = report["canonical_handoff"]
    assert handoff["runtime_identity_status"] == "canonical_runtime_active"
    assert handoff["runtime_active_codes"] == ["mojtaba-bot-ai"]
    assert handoff["canonical_missing_registered_tools"] == []
    assert handoff["legacy_unfinished_tasks"] == {
        "queued": 0, "running": 0, "blocked": 0,
    }
    assert handoff["source_and_registry_checks_passed"] is True
    assert handoff["live_cutover_authorized"] is False
    assert "live_scheduler_topology_not_attested" in handoff["blockers"]
    assert "vps_evolution_state_handoff_not_attested" in handoff["blockers"]
    assert (AgentTask.objects.count(), AuditLog.objects.count()) == before


@pytest.mark.django_db
def test_handoff_audit_blocks_legacy_queued_and_unregistered_canonical_tasks():
    old = Agent.objects.create(
        code="economic-master-agent", name="Old", mission="history", active=False,
    )
    canonical = Agent.objects.create(
        code="mojtaba-bot-ai", name="Current", mission="canonical", active=True,
    )
    pending = AgentTask.objects.create(
        agent=old, action_type="income_market_research", status="queued",
    )
    unknown = AgentTask.objects.create(
        agent=canonical, action_type="income_unregistered_execute",
        capability_code="income_unregistered_execute", status="queued",
    )
    before = (AgentTask.objects.count(), AuditLog.objects.count())
    out = StringIO()
    call_command("audit_agent_fleet", stdout=out)
    handoff = json.loads(out.getvalue())["canonical_handoff"]
    assert handoff["runtime_identity_status"] == "canonical_runtime_active"
    assert handoff["legacy_unfinished_tasks"]["queued"] == 1
    assert handoff["canonical_unsupported_queued_tasks"] == 1
    assert handoff["source_and_registry_checks_passed"] is False
    assert "unfinished_legacy_master_tasks_require_disposition" in handoff["blockers"]
    assert "canonical_queued_task_without_registered_handler" in handoff["blockers"]
    pending.refresh_from_db()
    unknown.refresh_from_db()
    assert pending.status == unknown.status == "queued"
    assert pending.attempt_count == unknown.attempt_count == 0
    assert (AgentTask.objects.count(), AuditLog.objects.count()) == before


@pytest.mark.django_db
def test_handoff_audit_blocks_both_master_runtimes_active():
    Agent.objects.create(
        code="economic-master-agent", name="Old", mission="legacy", active=True,
    )
    Agent.objects.create(
        code="mojtaba-bot-ai", name="Current", mission="canonical", active=True,
    )
    out = StringIO()
    call_command("audit_agent_fleet", stdout=out)
    handoff = json.loads(out.getvalue())["canonical_handoff"]
    assert handoff["runtime_identity_status"] == "multiple_active_runtime_identities_blocked"
    assert "multiple_active_master_runtimes" in handoff["blockers"]
    assert handoff["live_cutover_authorized"] is False

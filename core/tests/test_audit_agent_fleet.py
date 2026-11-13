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

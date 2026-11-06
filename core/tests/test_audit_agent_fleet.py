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
    before = (AgentTask.objects.count(), AuditLog.objects.count())

    output = StringIO()
    call_command("audit_agent_fleet", stdout=output)
    report = json.loads(output.getvalue())
    assert report["mode"] == "read_only"
    assert report["live_scheduler_attested"] is False
    assert report["verified_revenue_attested"] is False
    assert report["summary"]["unsupported_known_queue_tasks"] == 1
    assert report["summary"]["stale_running_tasks"] == 1
    rows = {row["code"]: row for row in report["agents"]}
    assert rows["economic-master-agent"]["known_registered_handlers"] == ["income_market_research"]
    assert "queued_task_not_supported_by_known_executor" in rows["economic-master-agent"]["findings"]
    assert "inactive_agent_has_pending_tasks" in rows["disabled-specialist"]["findings"]
    assert (AgentTask.objects.count(), AuditLog.objects.count()) == before


@pytest.mark.parametrize("kwargs", [
    {"days": 0}, {"days": 366}, {"stale_after": 0}, {"stale_after": 86401},
])
def test_fleet_audit_rejects_unbounded_options(kwargs):
    with pytest.raises(CommandError):
        call_command("audit_agent_fleet", **kwargs)

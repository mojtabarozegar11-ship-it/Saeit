import json
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from core.models import Agent, AgentCapability, AgentTask, AuditLog
from core.unified_bot_identity import BOT_CODE


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
    assert report["single_bot_contract"]["public_bot_id"] == "mojtaba.bot.ai"
    assert report["single_bot_contract"]["declared_top_level_bot_count"] == 1
    assert report["single_bot_contract"]["runtime_process_topology_attested"] is False
    assert report["single_bot_contract"]["economic_orchestrator_active"] is True
    assert report["live_scheduler_attested"] is False
    assert report["verified_revenue_attested"] is False
    assert report["summary"]["unsupported_known_queue_tasks"] == 1
    assert report["summary"]["stale_running_tasks"] == 1
    assert report["summary"]["exact_duplicate_role_groups"] == 1
    rows = {row["code"]: row for row in report["agents"]}
    assert all(row["public_bot_id"] == "mojtaba.bot.ai" for row in report["agents"])
    assert rows["economic-master-agent"]["known_registered_handlers"] == ["income_market_research"]
    assert "queued_task_not_supported_by_known_executor" in rows["economic-master-agent"]["findings"]
    assert "inactive_agent_has_pending_tasks" in rows["disabled-specialist"]["findings"]
    assert rows["duplicate-a"]["exact_role_duplicates"] == ["duplicate-b"]
    assert report["summary"]["django_records_classified"] == report["summary"]["agents_total"]
    assert report["summary"]["all_agents_live_disposition_verified"] is False
    assert report["summary"]["live_runtime_coverage_percent"] is None
    assert rows["economic-master-agent"]["disposition"]["state"] == "legacy_executor_migration_required"
    assert rows["disabled-specialist"]["disposition"]["state"] == "inactive_with_pending_work"
    assert all(
        row["disposition"]["target_bot_id"] == "mojtaba.bot.ai"
        and row["disposition"]["deactivation_or_deletion_authorized"] is False
        and row["disposition"]["external_runtime_attested"] is False
        for row in report["agents"]
    )
    assert (AgentTask.objects.count(), AuditLog.objects.count()) == before


@pytest.mark.parametrize("kwargs", [
    {"days": 0}, {"days": 366}, {"stale_after": 0}, {"stale_after": 86401},
])
def test_fleet_audit_rejects_unbounded_options(kwargs):
    with pytest.raises(CommandError):
        call_command("audit_agent_fleet", **kwargs)


@pytest.mark.parametrize("code,active,pending,legacy_decision,expected", [
    ("mojtaba-bot-ai", True, 0, None, "canonical_owner_active"),
    ("mojtaba-bot-ai", False, 0, None, "canonical_owner_inactive"),
    ("economic-master-agent", True, 0, None, "legacy_executor_migration_required"),
    ("moj_1ro_1", True, 1, None, "legacy_executor_migration_required"),
    ("newsletter-specialist", True, 0, "retire_safe", "legacy_retirement_candidate_unverified"),
    ("disabled-specialist", False, 1, None, "inactive_with_pending_work"),
    ("disabled-specialist", False, 0, None, "inactive_record_external_runtime_unknown"),
    ("unmapped-external-agent", True, 0, None, "component_dependency_inventory_required"),
])
def test_all_disposition_classes_are_fail_closed(code, active, pending, legacy_decision, expected):
    from core.management.commands.audit_agent_fleet import plan_agent_disposition

    row = {
        "code": code, "active": active,
        "legacy_consolidation_decision": legacy_decision,
        "tasks": {"pending": pending, "stale_running": 0},
        "capability_modules": {"outside": "unmapped_requires_adapter_review"},
    }
    decision = plan_agent_disposition(row)
    assert decision["target_bot_id"] == "mojtaba.bot.ai"
    assert decision["state"] == expected
    assert decision["deactivation_or_deletion_authorized"] is False
    assert decision["external_runtime_attested"] is False
    if code not in ("mojtaba-bot-ai",):
        assert "external_scheduler_and_process_topology_not_attested" in decision["blockers"]
    if pending:
        assert "pending_queued_running_or_blocked_tasks_need_reconciliation" in decision["blockers"]


@pytest.mark.django_db
def test_canonical_specialist_knowledge_queue_is_not_mislabelled_economic_unknown():
    owner = Agent.objects.create(
        code=BOT_CODE, name="Mojtaba.bot.ai", mission="Single owner", active=True,
    )
    cap = AgentCapability.objects.create(
        code="research-write-review", name="Knowledge generation", active=True,
    )
    cap.agents.add(owner)
    knowledge = AgentTask.objects.create(
        agent=owner, action_type="knowledge_content_generation",
        capability_code="research-write-review", risk_snapshot="high", status="queued",
    )
    unknown = AgentTask.objects.create(
        agent=owner, action_type="external_unknown_action",
        capability_code="research-write-review", status="queued",
    )
    before = (AgentTask.objects.count(), AuditLog.objects.count())
    output = StringIO()
    call_command("audit_agent_fleet", stdout=output)
    report = json.loads(output.getvalue())
    row = next(x for x in report["agents"] if x["code"] == BOT_CODE)
    assert row["capability_modules"]["research-write-review"] == "knowledge_library"
    assert row["tasks"]["queued_under_known_specialist_contract"] == 1
    assert row["tasks"]["queued_without_known_handler"] == 1
    assert report["summary"]["known_specialist_queued_not_live_attested"] == 1
    assert report["summary"]["unsupported_known_queue_tasks"] == 1
    assert report["external_delivery_attested"] is False
    assert report["full_consolidation_attested"] is False
    assert (AgentTask.objects.count(), AuditLog.objects.count()) == before
    knowledge.refresh_from_db()
    unknown.refresh_from_db()
    assert knowledge.status == unknown.status == "queued"

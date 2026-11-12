"""Read-only, evidence-bound inventory of the Django agent fleet.

Registered identities, available handlers and task receipts are different
things. This command deliberately makes no claim about live VPS scheduling,
external delivery, cash collection or the separate factory processes.
"""

import json
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from django.utils import timezone

from core.economic_tool_pack import build_economic_gateway
from core.management.commands.consolidate_legacy_agents import (
    LEGACY_AGENT_CODES, assess_agent,
)
from core.models import Agent, AgentTask
from core.bot_identity import BOT_ID, summarize_internal_agent_registry
from core.unified_bot_identity import (
    BOT_CODE, BOT_NAME, LEGACY_EXECUTOR_CODES,
    is_economic_capability, FACTORY_CAPABILITIES, module_for_capability,
)


EXECUTOR_SCOPES = {
    BOT_CODE: lambda code: is_economic_capability(code) or code in FACTORY_CAPABILITIES,
    "economic-master-agent": is_economic_capability,
    "moj_1ro_1": lambda code: code in FACTORY_CAPABILITIES,
}



def plan_agent_disposition(row):
    """Classify each Django Agent record without authorizing retirement.

    All noncanonical components require live scheduler / adapter inventory
    before a destructive or operational migration. An inactive database row
    never proves the external scheduler has stopped.
    """
    code = row["code"]
    active = row["active"]
    tasks = row["tasks"]
    if code == BOT_CODE:
        state = "canonical_owner_active" if active else "canonical_owner_inactive"
        route = "retain_canonical"
    elif not active and tasks["pending"]:
        state, route = "inactive_with_pending_work", "reconcile_and_migrate_tasks"
    elif not active:
        state, route = "inactive_record_external_runtime_unknown", "preserve_history"
    elif code in LEGACY_EXECUTOR_CODES:
        state, route = "legacy_executor_migration_required", "merge_into_canonical"
    elif row["legacy_consolidation_decision"] == "retire_safe":
        state, route = "legacy_retirement_candidate_unverified", "retire_after_verified_handoff"
    else:
        state, route = "component_dependency_inventory_required", "merge_or_retire_after_verification"

    blockers = []
    if code != BOT_CODE:
        blockers.append("external_scheduler_and_process_topology_not_attested")
    if tasks["pending"]:
        blockers.append("pending_queued_running_or_blocked_tasks_need_reconciliation")
    if tasks["stale_running"]:
        blockers.append("stale_task_effect_needs_reconciliation")
    if active and any(
        module == "unmapped_requires_adapter_review"
        for module in row["capability_modules"].values()
    ):
        blockers.append("capability_adapter_coverage_unverified")
    if code == BOT_CODE and not active:
        blockers.append("canonical_owner_not_active")

    return {
        "target_bot_id": BOT_ID,
        "state": state,
        "proposed_route": route,
        "blockers": blockers,
        "external_runtime_attested": False,
        "handoff_verified": False,
        "deactivation_or_deletion_authorized": False,
        "historical_records_must_be_preserved": True,
    }


class Command(BaseCommand):
    help = "Read-only agent inventory: task receipts, stalled work, known adapters and retirement evidence."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--stale-after", type=int, default=900)

    def handle(self, *args, **options):
        days = options["days"]
        stale_after = options["stale_after"]
        if not 1 <= days <= 365 or not 60 <= stale_after <= 86400:
            raise CommandError("days must be 1..365 and stale-after must be 60..86400")

        recent_cutoff = timezone.now() - timedelta(days=days)
        stale_cutoff = timezone.now() - timedelta(seconds=stale_after)
        gateway = build_economic_gateway()
        registered = {
            code for code, info in gateway.describe().items() if info["enabled"]
        }
        agents = []
        duplicate_signatures = {}
        for agent in Agent.objects.order_by("code").prefetch_related("capabilities"):
            tasks = AgentTask.objects.filter(agent=agent)
            active_caps = sorted(
                cap.code for cap in agent.capabilities.all() if cap.active
            )
            pending = tasks.filter(status__in=("queued", "running", "blocked")).count()
            stale = tasks.filter(status="running", updated_at__lte=stale_cutoff).count()
            recent = tasks.filter(status="completed", updated_at__gte=recent_cutoff).count()
            recent_newsletters = agent.newsletter_stories.filter(
                status="published", published_at__gte=recent_cutoff,
            ).count()
            known_scope = EXECUTOR_SCOPES.get(agent.code)
            known_handlers = sorted(
                cap for cap in active_caps
                if known_scope and cap in registered and known_scope(cap)
            )
            unsupported = None
            if known_scope:
                unsupported = tasks.filter(status="queued").exclude(
                    capability_code__in=known_handlers,
                    action_type=F("capability_code"),
                ).count()
            findings = []
            if not agent.active and pending:
                findings.append("inactive_agent_has_pending_tasks")
            if agent.active and not active_caps:
                findings.append("active_without_capabilities")
            if agent.active and known_scope and not known_handlers:
                findings.append("no_registered_handler_for_known_executor")
            if unsupported:
                findings.append("queued_task_not_supported_by_known_executor")
            if stale:
                findings.append("stale_running_tasks")
            if agent.active and not recent and not recent_newsletters:
                findings.append("no_recent_django_task_or_newsletter_receipt")
            legacy = assess_agent(agent)["decision"] if agent.code in LEGACY_AGENT_CODES else None
            if legacy == "retire_safe":
                findings.append("legacy_retirement_eligible_preview_only")

            agents.append({
                "code": agent.code,
                "public_bot_id": BOT_ID,
                "identity_scope": "internal_component_record_only",
                "active": agent.active,
                "bot_owner": BOT_NAME,
                "consolidation_state": (
                    "single_bot_owner" if agent.code == BOT_CODE else
                    "legacy_executor_inactive" if agent.code in LEGACY_EXECUTOR_CODES and not agent.active else
                    "legacy_executor_migration_required" if agent.code in LEGACY_EXECUTOR_CODES else
                    "internal_role_dependency_review_required"
                ),
                "capability_modules": {
                    cap: module_for_capability(cap) for cap in active_caps
                },
                "capabilities": active_caps,
                "known_registered_handlers": known_handlers,
                "handler_coverage": "partial_known_scope" if known_scope else "not_assessed_other_runtime",
                "tasks": {
                    "pending": pending,
                    "queued": tasks.filter(status="queued").count(),
                    "running": tasks.filter(status="running").count(),
                    "blocked": tasks.filter(status="blocked").count(),
                    "failed": tasks.filter(status="failed").count(),
                    "completed_recent": recent,
                    "published_newsletters_recent": recent_newsletters,
                    "stale_running": stale,
                    "queued_without_known_handler": unsupported,
                },
                "legacy_consolidation_decision": legacy,
                "exact_role_duplicates": [],
                "findings": findings,
            })

            # Only flag *exact* matches; similar names or a shared capability
            # are not proof that externally integrated agents are redundant.
            normalized_mission = " ".join((agent.mission or "").split()).casefold()
            if agent.active and active_caps and normalized_mission:
                duplicate_signatures.setdefault(
                    (normalized_mission, tuple(active_caps)), []
                ).append(agents[-1])

        for peers in duplicate_signatures.values():
            if len(peers) < 2:
                continue
            for row in peers:
                row["exact_role_duplicates"] = sorted(
                    other["code"] for other in peers if other is not row
                )
                row["findings"].append("exact_mission_and_capabilities_overlap_review_only")

        for row in agents:
            row["disposition"] = plan_agent_disposition(row)

        result = {
            "mode": "read_only",
            "single_bot_contract": summarize_internal_agent_registry(agents),
            "canonical_bot": {"code": BOT_CODE, "name": BOT_NAME},
            "days": days,
            "live_scheduler_attested": False,
            "full_consolidation_attested": False,
            "external_delivery_attested": False,
            "verified_revenue_attested": False,
            "note": "Django task receipts and handler registration do not prove execution on VPS or income.",
            "summary": {
                "agents_total": len(agents),
                "django_records_classified": sum(
                    bool(row.get("disposition")) for row in agents
                ),
                "active_noncanonical_pending_resolution": sum(
                    row["active"] and row["code"] != BOT_CODE for row in agents
                ),
                "inactive_records_external_runtime_unverified": sum(
                    not row["active"] and row["code"] != BOT_CODE for row in agents
                ),
                "retirement_candidates_needing_live_proof": sum(
                    row["disposition"]["state"] == "legacy_retirement_candidate_unverified"
                    for row in agents
                ),
                "live_runtime_coverage_percent": None,  # No VPS/process evidence read here.
                "all_agents_live_disposition_verified": False,
                "agents_active": sum(row["active"] for row in agents),
                "noncanonical_active_agent_rows": sum(
                    row["active"] and row["code"] != BOT_CODE for row in agents
                ),
                "unmapped_active_capabilities": sum(
                    module == "unmapped_requires_adapter_review"
                    for row in agents if row["active"]
                    for module in row["capability_modules"].values()
                ),
                "agents_with_findings": sum(bool(row["findings"]) for row in agents),
                "stale_running_tasks": sum(row["tasks"]["stale_running"] for row in agents),
                "unsupported_known_queue_tasks": sum(
                    row["tasks"]["queued_without_known_handler"] or 0 for row in agents
                ),
                "retirement_candidates": sum(
                    row["legacy_consolidation_decision"] == "retire_safe" for row in agents
                ),
                "exact_duplicate_role_groups": sum(
                    len(peers) > 1 for peers in duplicate_signatures.values()
                ),
            },
            "agents": agents,
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))

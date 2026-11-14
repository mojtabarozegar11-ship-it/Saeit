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
from core.canonical_bot_identity import (
    CANONICAL_BOT_CODE, LEGACY_RUNTIME_ALIASES, audit_identity_rows,
)
from core.management.commands.consolidate_legacy_agents import (
    LEGACY_AGENT_CODES, assess_agent,
)
from core.models import Agent, AgentTask


EXECUTOR_SCOPES = {
    CANONICAL_BOT_CODE: lambda code: code.startswith("income_") or code == "master_self_improvement",
    "economic-master-agent": lambda code: code.startswith("income_") or code == "master_self_improvement",
    "moj_1ro_1": lambda code: code in {"factory_native_review", "factory_f41_private_build"},
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
                "active": agent.active,
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

        # Repo/DB evidence only: never infer a live scheduler, safe rollback,
        # or permission to replace an existing runtime from a Django row.
        identity_audit = audit_identity_rows(Agent)
        canonical = Agent.objects.filter(
            code=CANONICAL_BOT_CODE, active=True,
        ).prefetch_related("capabilities").first()
        required_master_tools = {
            code for code in registered
            if code.startswith("income_") or code == "master_self_improvement"
        }
        enabled_canonical_tools = {
            cap.code for cap in canonical.capabilities.all() if cap.active
        } if canonical else set()
        missing_tools = sorted(required_master_tools - enabled_canonical_tools) if canonical else []
        legacy_unfinished = {
            status: AgentTask.objects.filter(
                agent__code__in=LEGACY_RUNTIME_ALIASES, status=status,
            ).count()
            for status in ("queued", "running", "blocked")
        }
        canonical_unsupported_queued = (
            AgentTask.objects.filter(agent=canonical, status="queued")
            .exclude(
                capability_code__in=enabled_canonical_tools & required_master_tools,
                action_type=F("capability_code"),
            ).count()
            if canonical is not None else 0
        )
        blockers = []
        if identity_audit["runtime_status"] == "multiple_active_runtime_identities_blocked":
            blockers.append("multiple_active_master_runtimes")
        if identity_audit["runtime_status"] == "no_active_master_runtime":
            blockers.append("no_active_master_runtime")
        if canonical is None:
            blockers.append("canonical_master_not_active")
        if any(legacy_unfinished.values()):
            blockers.append("unfinished_legacy_master_tasks_require_disposition")
        if missing_tools:
            blockers.append("canonical_master_missing_registered_tools")
        if canonical_unsupported_queued:
            blockers.append("canonical_queued_task_without_registered_handler")
        source_checks_passed = not blockers
        # Absence of host evidence is always a release blocker, even when
        # the source/DB check happens to pass.
        blockers.extend([
            "live_scheduler_topology_not_attested",
            "vps_evolution_state_handoff_not_attested",
            "rollback_and_recovery_not_attested",
        ])
        canonical_handoff = {
            "mode": "read_only",
            "runtime_identity_status": identity_audit["runtime_status"],
            "runtime_active_codes": identity_audit["runtime_active_codes"],
            "legacy_unfinished_tasks": legacy_unfinished,
            "canonical_missing_registered_tools": missing_tools,
            "canonical_unsupported_queued_tasks": canonical_unsupported_queued,
            "source_and_registry_checks_passed": source_checks_passed,
            "live_scheduler_attested": False,
            "vps_evolution_state_handoff_attested": False,
            "rollback_and_recovery_attested": False,
            "live_cutover_authorized": False,
            "blockers": blockers,
            "note": "Passing repository/registry checks never authorizes migration or deployment.",
        }

        result = {
            "mode": "read_only",
            "canonical_identity_audit": identity_audit,
            "canonical_handoff": canonical_handoff,
            "days": days,
            "live_scheduler_attested": False,
            "external_delivery_attested": False,
            "verified_revenue_attested": False,
            "note": "Django task receipts and handler registration do not prove execution on VPS or income.",
            "summary": {
                "agents_total": len(agents),
                "agents_active": sum(row["active"] for row in agents),
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
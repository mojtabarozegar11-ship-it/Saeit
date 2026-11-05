"""Retire explicitly identified legacy agent identities without losing history.

This is intentionally not an automatic 'delete every agent with zero sales'
command: operational agents can protect a site without directly earning money.
The known legacy roles below have been superseded by the central economic master
or the existing content workflow. Other agents need live evidence review.
"""

import json
import uuid

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Agent, AgentTask, AuditLog


LEGACY_AGENT_CODES = frozenset({
    "core_research",
    "newsletter-specialist",
    "newsletter-company-news",
    "newsletter-world-watch",
    "newsletter-unit-reports",
})
LEGACY_AGENT_PREFIXES = ("income-",)
PROTECTED_AGENT_CODES = frozenset({
    "economic-master-agent",
    "moj_1ro_1",
    "content-director",
    "knowledge-content-director",
})
ACTIVE_TASK_STATUSES = ("queued", "running", "blocked")
PENDING_NEWSLETTER_STATUSES = ("draft", "scheduled", "review", "queued", "processing")


def is_known_legacy(code):
    return code in LEGACY_AGENT_CODES or any(code.startswith(p) for p in LEGACY_AGENT_PREFIXES)


def assess_agent(agent):
    """Conservative classification using the *current* database, not a vanity score."""
    task_qs = AgentTask.objects.filter(agent=agent)
    active_tasks = task_qs.filter(status__in=ACTIVE_TASK_STATUSES).count()
    pending_stories = agent.newsletter_stories.filter(
        status__in=PENDING_NEWSLETTER_STATUSES
    ).count()
    protected = agent.code in PROTECTED_AGENT_CODES
    legacy = is_known_legacy(agent.code)

    if protected:
        decision = "retain_required"
    elif not legacy:
        decision = "review_live_outcomes"
    elif active_tasks or pending_stories:
        decision = "hold_for_dependency"
    elif agent.active:
        decision = "retire_safe"
    else:
        decision = "already_retired"

    return {
        "code": agent.code,
        "active": agent.active,
        "decision": decision,
        "active_tasks": active_tasks,
        "historical_tasks": task_qs.count(),
        "pending_stories": pending_stories,
        "financial_outcome": "not_assessed_from_task_counts",
    }


class Command(BaseCommand):
    help = (
        "Inventory agents; optionally retire only known legacy identities with "
        "no active tasks or pending stories, preserving historical rows."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Deactivate safe legacy agents")

    def handle(self, *args, **options):
        rows = []
        with transaction.atomic():
            agents = Agent.objects.select_for_update().order_by("code")
            for agent in agents:
                row = assess_agent(agent)
                if options["apply"] and row["decision"] == "retire_safe":
                    agent.active = False
                    agent.save(update_fields=["active", "updated_at"])
                    AuditLog.objects.create(
                        actor_type="system",
                        actor_id="agent-consolidation",
                        action="legacy_agent_retired",
                        target_type="Agent",
                        target_id=str(agent.pk),
                        before_state={"code": agent.code, "active": True},
                        after_state={
                            "code": agent.code,
                            "active": False,
                            "reason": "legacy_role_without_active_tasks_or_pending_stories",
                            "history_preserved": True,
                        },
                        trace_id=f"agent-retire-{agent.pk}-{uuid.uuid4().hex[:12]}",
                    )
                    row["decision"] = "retired"
                    row["active"] = False
                rows.append(row)

        self.stdout.write(json.dumps({
            "mode": "apply" if options["apply"] else "preview",
            "agents": rows,
            "summary": {
                "total": len(rows),
                "retired_now": sum(r["decision"] == "retired" for r in rows),
                "ready_to_retire": sum(r["decision"] == "retire_safe" for r in rows),
                "held_for_dependency": sum(r["decision"] == "hold_for_dependency" for r in rows),
                "unknown_requires_live_review": sum(r["decision"] == "review_live_outcomes" for r in rows),
            },
        }, ensure_ascii=False, default=str))

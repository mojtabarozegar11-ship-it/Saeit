"""Inventory and explicitly provision the canonical site-monitor owner.

Existing jobs and history are never reassigned by this preparatory command.
Run provisioning only during a reviewed maintenance window, with legacy
seeders stopped. It does not launch a runtime, create a scheduler, grant
economic/factory capabilities or retire any predecessor.
"""
import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count
from core.models import Agent, AgentTask
from core.unified_bot_identity import BOT_CODE, BOT_NAME

TERMINAL = ("completed", "failed", "cancelled")

def inventory():
    rows = []
    for agent in Agent.objects.order_by("code").prefetch_related("capabilities"):
        statuses = {r["status"]: r["total"] for r in AgentTask.objects.filter(
            agent=agent).values("status").annotate(total=Count("pk"))}
        pending = sum(n for status, n in statuses.items() if status not in TERMINAL)
        open_stories = agent.newsletter_stories.exclude(
            status__in=("published", "rejected", "cancelled")).count()
        distributions = agent.newsletter_stories.filter(
            publications__status__in=("queued", "blocked")).distinct().count()
        rows.append({"code": agent.code, "active": agent.active,
            "canonical": agent.code == BOT_CODE,
            "active_capabilities": sorted(c.code for c in agent.capabilities.all() if c.active),
            "tasks_by_status": statuses, "unreconciled_tasks": pending,
            "open_stories": open_stories, "pending_distributions": distributions,
            "runtime_verified": False, "retirement_authorized": False})
    return {"canonical_bot": BOT_CODE, "registered_agents": rows,
        "canonical_active": any(r["canonical"] and r["active"] for r in rows),
        "other_active_records": sum(r["active"] and not r["canonical"] for r in rows),
        "live_worker_count": None, "retirement_authorized": False}

class Command(BaseCommand):
    help = "Preview all Django agent handoff dependencies; explicitly prepare the one site owner."
    def add_arguments(self, parser):
        parser.add_argument("--provision-site-only", action="store_true")
        parser.add_argument("--confirm-maintenance-window", action="store_true")
    def handle(self, *args, **options):
        provision = options["provision_site_only"]
        confirmed = options["confirm_maintenance_window"]
        if provision != confirmed:
            raise CommandError("PROVISION_REQUIRES_CONFIRMED_MAINTENANCE_WINDOW")
        created = False
        if provision:
            with transaction.atomic(durable=True):
                agent, created = Agent.objects.get_or_create(code=BOT_CODE,
                    defaults={"name": BOT_NAME,
                    "mission": "Canonical owner of bounded site observability",
                    "risk_level": "low", "active": True})
                if not created and not agent.active:
                    raise CommandError("EXISTING_CANONICAL_INACTIVE_REVIEW_REQUIRED")
                # No capability grants, update of existing agent, task mutation,
                # factory launch or legacy deactivation.
        result = inventory()
        result.update({"canonical_record_created": created, "runtime_started": False,
                       "agents_retired": 0, "factory_started": False})
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))

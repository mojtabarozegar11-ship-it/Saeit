"""Read-only gate census for the single Mojtaba.bot.ai product identity.

Use: python manage.py mojtaba_runtime_inventory --database default

This command neither provisions a canonical Agent row nor starts, stops, migrates,
retires, retries, schedules or grants any task. Historical agent records are
inventory evidence only, not proof of independently running bots.
"""
import importlib.util
import json
import os

from django.core.management.base import BaseCommand
from django.db.models import Count

from core.models import Agent, AgentTask, ChatMessage, ChatSession
from core.unified_bot_identity import BOT_CODE
from mojtaba_identity import BOT_ID


TERMINAL_TASK_STATES = ("completed", "failed", "cancelled")


def inventory(*, using="default"):
    """Gather counts from an existing Django DB alias, with SELECT queries only."""
    agents = list(
        Agent.objects.using(using)
        .order_by("code")
        .values("code", "active")
    )
    by_code = {}
    for agent in agents:
        code = agent["code"]
        by_code[code] = by_code.get(code, 0) + 1

    pending_rows = list(
        AgentTask.objects.using(using)
        .exclude(status__in=TERMINAL_TASK_STATES)
        .values("agent__code", "status")
        .annotate(count=Count("pk"))
        .order_by("agent__code", "status")
    )
    pending = [
        {"agent_code": item["agent__code"],
         "status": item["status"],
         "count": int(item["count"])}
        for item in pending_rows
    ]
    canonical_rows = by_code.get(BOT_CODE, 0)
    canonical_active = sum(
        1 for item in agents
        if item["code"] == BOT_CODE and item["active"] is True
    )
    source_runtime_present = importlib.util.find_spec(
        "core.mojtaba_host_runtime"
    ) is not None
    key_present = bool(os.environ.get("OPENAI_API_KEY"))
    # No presence flag, config key, registered Agent, HTTP page or task count
    # can prove a live worker. Evidence of a real operator interaction is needed.
    return {
        "product_id": BOT_ID,
        "scope": "read_only_django_registry_not_a_live_worker_attestation",
        "database_alias": using,
        "registered_agent_rows": len(agents),
        "active_agent_rows": sum(1 for item in agents if item["active"] is True),
        "registered_codes": sorted(by_code),
        "canonical_agent_code": BOT_CODE,
        "canonical_agent_rows": canonical_rows,
        "canonical_active_rows": canonical_active,
        "nonterminal_task_count": sum(item["count"] for item in pending),
        "nonterminal_tasks_by_agent_and_status": pending,
        "chat_session_count": ChatSession.objects.using(using).count(),
        "chat_message_count": ChatMessage.objects.using(using).count(),
        "code_runtime_module_available": source_runtime_present,
        "model_api_key_configured_in_command_process": key_present,
        "single_worker_attested": False,
        "authenticated_inference_attested": False,
        "automatic_migration_authorized": False,
        "legacy_agents_deactivated": False,
        "income_attested": False,
        "release_gate": "BLOCKED_NEEDS_RUNTIME_HANDOFF_AND_LIVE_RECEIPT",
    }


class Command(BaseCommand):
    help = "Read-only registry census for Mojtaba.bot.ai; never runs or migrates agents"

    def add_arguments(self, parser):
        parser.add_argument(
            "--database", default="default",
            help="Existing configured Django database alias (default: default)"
        )

    def handle(self, *args, **options):
        report = inventory(using=options["database"])
        self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))

"""Owner's existing Mojtaba.bot.ai CRM-to-desk recovery control.

Default: read-only preview. Explicit --apply: bounded internal handoff only.
No customer email/SMS, public publishing, invoice, price, payment or trading.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from core.service_lead_handoff import (
    orphaned_handoff_snapshot,
    recover_one_orphaned_handoff,
)

MAX_APPLY = 20


class Command(BaseCommand):
    help = "Recover consented and independently audited prepared CRM scopes into real owner WorkItems."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--limit", type=int, default=1)

    def handle(self, *args, **options):
        limit = options["limit"]
        if type(limit) is not int or not 1 <= limit <= MAX_APPLY:
            raise CommandError("limit must be a real integer from 1 to 20")

        if not options["apply"]:
            snapshot = orphaned_handoff_snapshot()
            output = {
                "bot": "mojtaba.bot.ai",
                "mode": "read_only",
                "eligible_verified_handoffs": snapshot["verified_candidate_count"],
                "queue_total": snapshot["queue_total"],
                "queue_inspected": snapshot["inspected"],
                "queue_uninspected": snapshot["uninspected"],
                "scan_complete": snapshot["scan_complete"],
                "writes_performed": 0,
                "customer_contacted": False,
                "cash_received": None,
            }
            self.stdout.write(json.dumps(output, sort_keys=True))
            return

        created = []
        blocked = "none"
        for _ in range(limit):
            result = recover_one_orphaned_handoff()
            if result.get("verified_effect") is True:
                created.append(result["evidence"]["workitem_id"])
            else:
                blocked = result["state"]
                break
        self.stdout.write(json.dumps({
            "bot": "mojtaba.bot.ai",
            "mode": "internal_desk_handoff_only",
            "created_workitem_count": len(created),
            "created_workitem_ids": created,
            "blocked_reason": blocked,
            "customer_contacted": False,
            "published_price": False,
            "invoices_created": 0,
            "external_cash_settlement": None,
            "deployment_performed": False,
        }, sort_keys=True))

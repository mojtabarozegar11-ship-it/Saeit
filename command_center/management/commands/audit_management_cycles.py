"""Cron-safe, read-only management and accounting watchdog.

This command does not advance C01-C50 counters, create completion records,
change financial documents, send messages, or call any external service.
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from command_center.integrated_ledger_api import cycle_health, _finance_integrity


class Command(BaseCommand):
    help = "Emit one factual management/ledger health snapshot as JSON, without writes"

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="Return nonzero when verified integrity or overdue-work problems exist")

    def handle(self, *args, **options):
        cycles = cycle_health()
        finance = _finance_integrity()
        payload = {
            "observed_at": timezone.now().isoformat(),
            "mode": "read_only",
            "cycle_health": cycles,
            "finance_integrity": finance,
            "alerts": [],
        }
        if not finance["balanced_posted_entries"]:
            payload["alerts"].append("POSTED_JOURNAL_IMBALANCE")
        if cycles["overdue_open_work"]:
            payload["alerts"].append("OVERDUE_WORK")
        if cycles["pending_owner_approval"]:
            payload["alerts"].append("OWNER_APPROVAL_PENDING")
        if cycles["no_result_reference"]:
            payload["alerts"].append("WORK_WITHOUT_RESULT_REFERENCE")
        if cycles["done_without_evidence"]:
            payload["alerts"].append("COMPLETION_WITHOUT_EVIDENCE")
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        if options["strict"] and any(x in payload["alerts"] for x in ("POSTED_JOURNAL_IMBALANCE", "OVERDUE_WORK")):
            raise CommandError("Verified accounting integrity or overdue-work exception")

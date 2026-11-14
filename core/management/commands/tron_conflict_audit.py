"""Read-only, bounded, non-PII TRX settlement conflict audit.

Never reconciles an invoice, modifies the ledger, sends email or authorizes
production. Must be run against the *effective* merchant DB to be meaningful.
"""
import json

from django.core.management.base import BaseCommand

from core.models import LedgerEntry, PaymentWebhookEvent
from core.tron_tx_conflict_audit import summarize_tron_conflicts


class Command(BaseCommand):
    help = "Read-only TRX cross-provider duplicate-credit evidence (redacted)"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5000)

    def handle(self, *args, **options):
        limit = options["limit"]
        if type(limit) is not int or not 1 <= limit <= 20000:
            raise ValueError("Invalid bounded audit limit")

        # These two SQL queries read committed records without selecting a
        # whole merchant database or serializing sensitive buyer identities.
        events = list(PaymentWebhookEvent.objects.filter(
            event_type="tron_finalized"
        ).order_by("pk").values(
            "event_id", "provider", "status",
        )[:limit + 1])
        credits = list(LedgerEntry.objects.filter(
            entry_type="credit", reference__icontains="tron-mainnet:"
        ).order_by("pk").values(
            "reference",
        )[:limit + 1])

        complete = len(events) <= limit and len(credits) <= limit
        evidence = summarize_tron_conflicts(
            events[:limit], credits[:limit], complete=complete,
        )
        evidence["scope"] = "bounded-persisted-tron-events-and-credits"
        evidence["live_runtime_verified"] = False
        self.stdout.write("TRON_CONFLICT_AUDIT=" + json.dumps(
            evidence, sort_keys=True, separators=(",", ":"),
        ))

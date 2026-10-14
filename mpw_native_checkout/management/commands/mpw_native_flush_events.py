"""Retry signed checkout notifications from private Django outbox.

This command is intentionally NOT placed in production crontab yet. The live
checkout must first be approved and integrated. When there is no pending event,
only a local indexed database query is made (zero blockchain/AI API calls).
"""
from django.core.management.base import BaseCommand
from mpw_native_checkout.purchase_notify import flush_pending_watch_events


class Command(BaseCommand):
    help = "Deliver pending native-coin purchase wake/close messages, no chain polling."

    def handle(self, *args, **options):
        result = flush_pending_watch_events(limit=20)
        self.stdout.write(
            "MPW_NATIVE_EVENT_OUTBOX "
            + result["state"]
            + " attempted=" + str(result["attempted"])
            + " no_ai_requests=true"
        )

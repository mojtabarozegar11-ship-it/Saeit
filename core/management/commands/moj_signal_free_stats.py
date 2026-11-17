"""Privacy-safe verified free educational membership evidence.

Counts only persistent confirmed states, never counts them as customers or sales.
Read-only; no sending, publishing, payments, analytics identifiers or PII.
"""
import json

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from core.signal_free_models import MojSignalFreeSubscription


class Command(BaseCommand):
    help = "Count truly confirmed free educational opt-ins without exposing emails."

    def handle(self, *args, **options):
        counts = dict(
            MojSignalFreeSubscription.objects.values("status")
            .annotate(n=Count("pk")).values_list("status", "n")
        )
        output = {
            "schema": "mojtaba.signal.free_audience.v1",
            "as_of_utc": timezone.now().isoformat(),
            "agent": "mojtaba.bot.ai",
            "pending_email_confirmation": counts.get("pending", 0),
            "confirmed_free_members": counts.get("confirmed", 0),
            "unsubscribed_suppressed": counts.get("unsubscribed", 0),
            "paid_customers_verified": None,
            "settled_revenue_usd": None,
            "automatic_marketing_delivery": False,
            "note": "Free members are not paid customers; sender/SMTP and editorial publication remain separate release gates.",
        }
        self.stdout.write(json.dumps(output, ensure_ascii=False, sort_keys=True))

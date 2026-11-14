"""Read-only triage for uncertain company-trade email delivery.

Never retries, repairs, requeues, sends, consumes owner grants or discloses
recipient addresses, message text, subjects, credential values or tokens.
"""
import json
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.economic_trade_models import TradeEmailAudit, TradeEmailOutbox


UNRESOLVED = ("dispatching", "delivery_unknown")


class Command(BaseCommand):
    help = "Read-only company-trade outbox dispatch reconciliation inventory"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--stale-after", type=int, default=900)

    def handle(self, *args, **options):
        limit = options["limit"]
        stale_after = options["stale_after"]
        if isinstance(limit, bool) or not 1 <= limit <= 100:
            raise CommandError("limit must be 1..100")
        if isinstance(stale_after, bool) or not 60 <= stale_after <= 86400:
            raise CommandError("stale-after must be 60..86400")
        now = timezone.now()
        queue = TradeEmailOutbox.objects.filter(
            mailbox__code="company-trade", status__in=UNRESOLVED,
        )
        counts = {
            code: queue.filter(status=code).count() for code in UNRESOLVED
        }
        rows = list(
            queue.select_related("mailbox").order_by("updated_at", "pk")[:limit]
        )
        reserved = set(
            TradeEmailAudit.objects.filter(
                outbox_id__in=[row.pk for row in rows],
                action="dispatch_reserved",
            ).values_list("outbox_id", flat=True)
        )
        entries = []
        for item in rows:
            age = max(0, int((now - item.updated_at).total_seconds()))
            entries.append({
                "outbox_id": item.pk,
                "status": item.status,
                "age_seconds": age,
                "dispatch_reservation_recorded": item.pk in reserved,
                "requires_manual_reconciliation": True,
                "stale_dispatch": (
                    item.status == "dispatching" and age >= stale_after
                ),
                "review_reason": (
                    "crash_or_ongoing_dispatch_check"
                    if item.status == "dispatching"
                    else "provider_delivery_not_confirmed"
                ),
            })
        total = sum(counts.values())
        self.stdout.write(json.dumps({
            "mode": "read_only",
            "scope": "company-trade",
            "observed_at": now.isoformat(),
            "automated_retry_allowed": False,
            "send_performed": False,
            "owner_approval_consumed": False,
            "unresolved_total": total,
            "counts": counts,
            "returned_count": len(entries),
            "truncated": total > len(entries),
            "items": entries,
            "note": "Never requeue or resend without independently reconciled provider evidence and new owner authorization.",
        }, ensure_ascii=False, sort_keys=True))

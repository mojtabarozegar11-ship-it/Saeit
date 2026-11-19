"""Bounded server-side settlement of existing MojPlayWin invoices.
Invoke from the approved production scheduler, not GitHub Actions.
Never issue invoices, transmit TRX, send mail or accept client-supplied proofs.
"""
from datetime import timedelta
import json

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, IntegrityError
from django.utils import timezone

from core.models import PaymentIntent
from services.mpw_trx_walletless_core import PaymentHold
from services.mpw_walletless_commercial_intent import (
    PROVIDER, WAITING, _paid_read_db, reconcile_commercial_intent_from_candidates,
)
from services.mpw_tron_readonly_deposit_candidates import find_candidate_hashes
from services.mpw_trx_commercial_chain import read_only_independent_pair


class Command(BaseCommand):
    help = "Reconcile existing owner-issued TRX invoices in bounded cursor batches."

    def add_arguments(self, parser):
        parser.add_argument("--after-id", type=int, default=0)
        parser.add_argument("--limit", type=int, default=5)
        parser.add_argument("--lookback-hours", type=int, default=168)

    def handle(self, *args, **options):
        cursor, limit, hours = (options["after_id"], options["limit"],
                                options["lookback_hours"])
        if not (cursor >= 0 and 1 <= limit <= 10 and 1 <= hours <= 168):
            raise CommandError("Invalid bounded reconciliation batch")
        if getattr(settings, "MPW_TRX_BACKGROUND_RECONCILE_ENABLED", False) is not True:
            raise CommandError("Production background reconciliation is not approved")
        try:
            _paid_read_db(settings, connection)
        except PaymentHold as exc:
            raise CommandError("Production paid-read gate unavailable") from exc
        rows = list(PaymentIntent.objects.filter(
            provider=PROVIDER, status=WAITING, pk__gt=cursor,
            created_at__gte=timezone.now() - timedelta(hours=hours),
        ).order_by("pk").values_list("pk", "order__customer_id")[:limit])
        result = {"scanned": len(rows), "paid": 0, "pending": 0,
                  "deferred": 0, "next_after_id": 0}
        if rows:
            try:
                pair = read_only_independent_pair()
            except (PaymentHold, OSError, ValueError):
                raise CommandError("Independent finalized RPC unavailable") from None
            for invoice_id, buyer_id in rows:
                if not cache.add(f"mpw-trx-reconcile:{invoice_id}", 1, timeout=90):
                    result["deferred"] += 1
                    continue
                try:
                    outcome = reconcile_commercial_intent_from_candidates(
                        invoice_id, buyer_id, server_lookup=find_candidate_hashes, pair=pair,
                    )
                    result["paid" if outcome == "paid" else "pending"] += 1
                except (PaymentHold, OSError, ValueError, IntegrityError):
                    result["deferred"] += 1
            result["next_after_id"] = rows[-1][0] if len(rows) == limit else 0
        self.stdout.write(json.dumps(result, sort_keys=True))

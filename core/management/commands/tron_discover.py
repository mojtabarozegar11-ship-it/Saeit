"""Bounded read-only incoming-TRX discovery for owner-authorized merchant worker.

This command requires an explicitly enabled and properly keyed account-history
indexer. The indexer only suggests hashes; independent finalized-node proof
remains mandatory. The command does not create invoices or broadcast transfers.
"""
from __future__ import annotations

import time
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db.models import F
from django.utils import timezone

from core.tron_gateway_invoice import TronGatewayInvoice
from core.tron_gateway_verify import PaymentNotFinal, verify_native_trx
from core.tron_gateway_merchant_registry import configured_site_merchant, MerchantConfigurationError
from core.tron_gateway_discovery import receiver_candidates
from core.tron_gateway_web import _record_paid


class Command(BaseCommand):
    help = "Find candidate incoming native TRX and credit only dual-solidified matching invoices"

    def add_arguments(self, parser):
        parser.add_argument("--pages", type=int, default=3)
        parser.add_argument("--max-checks", type=int, default=12)

    def handle(self, *args, **options):
        if getattr(settings, "TRON_UNIFIED_DISCOVERY_ENABLED", False) is not True:
            self.stdout.write("tron_discover disabled")
            return
        pages, max_checks = options["pages"], options["max_checks"]
        if not 1 <= pages <= 5 or not 1 <= max_checks <= 25:
            raise ValueError("Unbounded TRX discovery parameters")
        now_ms = int(time.time() * 1000)
        # Older invoices remain recoverable through submitted txid reconciliation.
        recent = list(TronGatewayInvoice.objects.filter(
            status="awaiting_payment",
            issued_ms__gte=now_ms - 48 * 3600 * 1000,
        ).order_by("-issued_ms")[:500])
        if not recent:
            self.stdout.write("tron_discover pending=0")
            return
        # A deposit is never matched across different registered receivers or
        # merchant tenants, even when invoice SUN values happen to coincide.
        # Bounded to four receiver groups per invocation to prevent runaway
        # indexer costs from a large number of approved site/subsite wallets.
        by_receiver = defaultdict(list)
        held_invalid_registry = 0
        registry = getattr(settings, "TRON_UNIFIED_SITE_MERCHANTS", {})
        for inv in recent:
            try:
                merchant = configured_site_merchant(inv.source_host, registry)
            except MerchantConfigurationError:
                held_invalid_registry += 1
                continue
            if (inv.merchant_tenant_id != merchant.tenant_id
                    or inv.receiver != merchant.receiver):
                held_invalid_registry += 1
                continue
            by_receiver[inv.receiver].append(inv)
        receiver_groups = sorted(
            by_receiver,
            key=lambda receiver: min(x.issued_ms for x in by_receiver[receiver]),
        )
        omitted_receivers = max(0, len(receiver_groups) - 4)
        candidates = []
        seen_invoice = set()
        discovered_count = 0
        truncated = omitted_receivers > 0
        indexer_unavailable = 0
        for receiver in receiver_groups[:4]:
            invoices = by_receiver[receiver]
            try:
                discovered, was_truncated = receiver_candidates(
                    min_ms=max(1, min(x.issued_ms for x in invoices) - 10_000),
                    max_ms=now_ms, pages=pages, receiver=receiver,
                )
            except PaymentNotFinal:
                indexer_unavailable += 1
                continue
            discovered_count += len(discovered)
            truncated = truncated or was_truncated
            by_amount = defaultdict(list)
            for inv in invoices:
                by_amount[inv.amount_sun].append(inv)
            for txid, sun, stamp in discovered:
                for inv in by_amount.get(sun, ()):
                    if inv.pk in seen_invoice:
                        continue
                    if not inv.issued_ms - 10_000 <= stamp <= inv.expires_ms + 60_000:
                        continue
                    seen_invoice.add(inv.pk)
                    candidates.append((inv, txid))
        # Fairness: rotate older failed checks instead of starving new buyers.
        candidates.sort(key=lambda pair: (
            pair[0].reconcile_attempted_at is not None,
            pair[0].reconcile_attempted_at or timezone.now(),
            pair[0].pk))
        inspected = paid = held = 0
        for inv, txid in candidates[:max_checks]:
            inspected += 1
            TronGatewayInvoice.objects.filter(
                pk=inv.pk, status="awaiting_payment").update(
                    candidate_txid=txid,
                    reconcile_attempted_at=timezone.now(),
                    reconcile_attempts=F("reconcile_attempts") + 1)
            try:
                proof = verify_native_trx(
                    txid, inv.receiver, inv.amount_sun,
                    inv.issued_ms, inv.expires_ms)
                if _record_paid(inv.pk, proof):
                    paid += 1
                else:
                    held += 1
            except (PaymentNotFinal, IntegrityError, ValueError, OSError):
                held += 1
        self.stdout.write(
            f"tron_discover candidate_count={discovered_count} "
            f"matched={len(candidates)} receivers_checked={min(4,len(receiver_groups))} "
            f"receivers_omitted={omitted_receivers} invalid_tenant_holds={held_invalid_registry} "
            f"indexer_unavailable={indexer_unavailable} inspected={inspected} "
            f"paid={paid} held={held} "
            f"truncated={int(truncated or len(candidates) > max_checks)}")

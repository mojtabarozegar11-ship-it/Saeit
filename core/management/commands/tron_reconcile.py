"""Recheck customer-submitted TRX txids after RPC outages.

A 1-minute cron can safely invoke this command. It does not broadcast funds,
issue payable invoices or rely on a screenshot or buyer statement as proof.
"""
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db.models import F
from django.utils import timezone

from core.tron_gateway_invoice import TronGatewayInvoice
from core.tron_gateway_verify import PaymentNotFinal, TX_PATTERN, verify_native_trx
from core.tron_gateway_web import _record_paid


class Command(BaseCommand):
    help = "Independently reconcile submitted native TRX hashes into existing invoices"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        count = options["limit"]
        if not 1 <= count <= 1000:
            raise ValueError("Limit must be between 1 and 1000")
        # Least-recently-attempted first, so an unavailable old transfer never
        # prevents a later valid customer invoice from being processed.
        invoices = list(TronGatewayInvoice.objects.filter(
            status="awaiting_payment").exclude(candidate_txid="").order_by(
                "reconcile_attempted_at", "id")[:count])
        attempted = settled = held = 0
        for invoice in invoices:
            attempted += 1
            TronGatewayInvoice.objects.filter(pk=invoice.pk, status="awaiting_payment").update(
                reconcile_attempted_at=timezone.now(),
                reconcile_attempts=F("reconcile_attempts") + 1)
            tx = invoice.candidate_txid
            if not TX_PATTERN.fullmatch(tx):
                held += 1
                continue
            try:
                proof = verify_native_trx(
                    tx, invoice.receiver, invoice.amount_sun,
                    invoice.issued_ms, invoice.expires_ms)
                if _record_paid(invoice.pk, proof):
                    settled += 1
                else:
                    held += 1
            except (PaymentNotFinal, IntegrityError, ValueError, OSError):
                held += 1
        self.stdout.write(
            f"tron_reconcile attempted={attempted} paid={settled} held={held}")

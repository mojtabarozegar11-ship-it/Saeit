"""Read-only chain checks for already-submitted invoices; no withdrawals or swaps.

Run from a verified, MojPlayWin-isolated scheduler every few minutes.
"""
from django.core.management.base import BaseCommand
from core.mojplaywin_crypto_models import MojCryptoInvoice
from core.mojplaywin_crypto_gateway import settle
from core.mojplaywin_chain_verify import VerificationError
from django.conf import settings


class Command(BaseCommand):
    help = "Safely reconcile pending MojPlayWin ETH/TRX invoices with submitted hashes"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=30)

    def handle(self, *args, **options):
        if not getattr(settings, "MOJPLAYWIN_CRYPTO_ENABLED", False):
            self.stdout.write("MOJPLAYWIN_CRYPTO_ENABLED=false; no changes.")
            return
        invoices = MojCryptoInvoice.objects.filter(
            status="confirming", tx_hash__isnull=False,
        ).order_by("created_at")[:max(1, min(options["limit"], 100))]
        processed = 0
        for invoice in invoices:
            try:
                settle(invoice.pk, invoice.tx_hash)
                processed += 1
            except VerificationError:
                # Keep claim pending; false evidence must never credit an invoice.
                continue
        self.stdout.write(f"Reconciled {processed} invoices, after verified confirmations.")

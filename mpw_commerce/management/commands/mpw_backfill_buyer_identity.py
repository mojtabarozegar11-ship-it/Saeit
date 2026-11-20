"""Evidence-only backfill for the staff buyer identity projection."""
from django.core.management.base import BaseCommand

from core.models import GuestOrderEmail, LedgerEntry
from core.crown_tron_receipts import verified_walletless_credit
from mpw_commerce.buyer_identity import BuyerIdentityConflict, record_buyer_identity
from mpw_commerce.models import CommerceReceipt


class Command(BaseCommand):
    help = (
        "Backfill buyer email and verified payer wallet into CommerceBuyerIdentity. "
        "Read-only unless --commit is supplied."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Write only identities supported by existing independent evidence.",
        )

    def handle(self, *args, **options):
        commit = bool(options["commit"])
        email_candidates = wallet_candidates = 0
        email_written = wallet_written = conflicts = 0

        for claim in GuestOrderEmail.objects.select_related("order").order_by("pk"):
            email_candidates += 1
            if not commit:
                continue
            try:
                record_buyer_identity(
                    order=claim.order,
                    email=claim.email_address,
                    source="checkout_email_backfill",
                )
                email_written += 1
            except BuyerIdentityConflict:
                conflicts += 1

        for receipt in CommerceReceipt.objects.select_related("invoice__order").order_by("pk"):
            invoice = receipt.invoice
            if invoice.status != "paid":
                continue
            wallet_candidates += 1
            if not commit:
                continue
            try:
                record_buyer_identity(
                    order=invoice.order,
                    payer_wallet=receipt.sender,
                    network=receipt.network,
                    tx_hash=receipt.tx_hash,
                    source="verified_commerce_receipt_backfill",
                    verified_at=receipt.finalized_at,
                )
                wallet_written += 1
            except BuyerIdentityConflict:
                conflicts += 1

        for entry in LedgerEntry.objects.select_related(
            "order", "payment_intent"
        ).filter(entry_type="credit").order_by("pk"):
            intent = entry.payment_intent
            if intent is None:
                continue
            try:
                verified = verified_walletless_credit(entry.order, intent) is True
            except Exception:
                verified = False
            if not verified:
                continue
            metadata = entry.metadata if isinstance(entry.metadata, dict) else {}
            sender = metadata.get("sender")
            network = metadata.get("network", "")
            tx_hash = metadata.get("tx_hash", "")
            if not all(isinstance(value, str) and value for value in (sender, network, tx_hash)):
                continue
            wallet_candidates += 1
            if not commit:
                continue
            try:
                record_buyer_identity(
                    order=entry.order,
                    payer_wallet=sender,
                    network=network,
                    tx_hash=tx_hash,
                    source="verified_walletless_receipt_backfill",
                    verified_at=entry.created_at,
                )
                wallet_written += 1
            except BuyerIdentityConflict:
                conflicts += 1

        mode = "commit" if commit else "dry-run"
        self.stdout.write(
            self.style.SUCCESS(
                "buyer_identity_backfill "
                f"mode={mode} email_candidates={email_candidates} "
                f"wallet_candidates={wallet_candidates} "
                f"email_written={email_written} wallet_written={wallet_written} "
                f"conflicts={conflicts}"
            )
        )

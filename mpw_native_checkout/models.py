"""Native ETH/TRX invoice reservation and blockchain proof storage.

Staging app: NOT included in production INSTALLED_APPS or URL routing.
Payment decisions must come from independently verified chain evidence.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class NativeInvoice(models.Model):
    class Asset(models.TextChoices):
        ETH = "ETH", "Ether (Ethereum Mainnet)"
        TRX = "TRX", "TRX (TRON Mainnet)"

    class Status(models.TextChoices):
        AWAITING = "awaiting", "Awaiting blockchain payment"
        PAID = "paid", "Verified and paid"
        EXPIRED = "expired", "Invoice expired"
        REFUND_REVIEW = "refund_review", "Manual refund review"

    order = models.OneToOneField("core.Order", on_delete=models.PROTECT, related_name="native_coin_invoice")
    product = models.ForeignKey("core.Product", on_delete=models.PROTECT)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    asset = models.CharField(max_length=3, choices=Asset.choices)
    network = models.CharField(max_length=32)
    merchant_address = models.CharField(max_length=100)
    verified_sender_address = models.CharField(max_length=100)
    # EVM Wei and TRON Sun. Decimal 0 is deliberately used instead of floating point.
    amount_atomic = models.DecimalField(max_digits=50, decimal_places=0)
    usd_amount = models.DecimalField(max_digits=14, decimal_places=2)
    usd_per_asset = models.DecimalField(max_digits=30, decimal_places=12)
    price_source = models.CharField(max_length=40)
    price_observed_at = models.DateTimeField()
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    wallet_challenge_id = models.CharField(max_length=128)
    sender_signature_verified_at = models.DateTimeField()
    merchant_ownership_verified_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.AWAITING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["network", "merchant_address", "amount_atomic"],
                name="mpw_native_unique_invoice_amount",
            ),
            models.CheckConstraint(condition=Q(amount_atomic__gt=0), name="mpw_native_invoice_positive"),
            models.CheckConstraint(condition=Q(usd_amount__gt=0), name="mpw_native_invoice_positive_usd"),
        ]


class NativeChainTransfer(models.Model):
    """One chain transaction can settle at most one invoice, enforced by SQL."""

    invoice = models.OneToOneField(NativeInvoice, on_delete=models.PROTECT, related_name="chain_transfer")
    network = models.CharField(max_length=32)
    tx_hash = models.CharField(max_length=80)  # always lower-cased by service
    sender_address = models.CharField(max_length=100)
    recipient_address = models.CharField(max_length=100)
    amount_atomic = models.DecimalField(max_digits=50, decimal_places=0)
    verified_at = models.DateTimeField()
    verification_backend = models.CharField(max_length=64)
    evidence_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["network", "tx_hash"], name="mpw_native_unique_chain_tx"),
            models.CheckConstraint(condition=Q(amount_atomic__gt=0), name="mpw_native_transfer_positive"),
        ]

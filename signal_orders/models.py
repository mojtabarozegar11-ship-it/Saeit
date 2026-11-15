"""Immutable-at-service-boundary pending order records. No settlement fields."""
from django.db import models


class PendingSignalOrderRecord(models.Model):
    """Only hashed buyer reference and contract payload, never a raw buyer email."""

    order_id = models.CharField(max_length=64, unique=True, editable=False)
    tenant_id = models.CharField(max_length=64, db_index=True, editable=False)
    offer_id = models.CharField(max_length=64, editable=False)
    payload_digest = models.CharField(max_length=64, editable=False)
    payload = models.JSONField(editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        db_table = "mojtaba_signal_pending_orders"
        default_permissions = ("view",)
        indexes = [
            models.Index(fields=("tenant_id", "created_at"), name="sig_ord_tenant_time_idx"),
        ]

    def __str__(self):
        return self.order_id


class PendingSignalTrxQuote(models.Model):
    """Unique quote proposal per order, not a chain invoice or settled receipt.

    The signed token contains no raw buyer email or private signing key.
    A unique FK stops concurrent quotes to multiple payment destinations.
    """
    order = models.OneToOneField(
        PendingSignalOrderRecord, related_name="trx_quote",
        on_delete=models.PROTECT,
    )
    invoice_id = models.CharField(max_length=64, unique=True, editable=False)
    signed_token = models.TextField(editable=False)
    token_digest = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        db_table = "mojtaba_signal_trx_quote_proposals"
        default_permissions = ("view",)

    def __str__(self):
        return self.invoice_id

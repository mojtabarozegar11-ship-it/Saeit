"""Persisted audit trail for cross-site, email-only native TRX invoices."""
from django.db import models


class TronGatewayInvoice(models.Model):
    order = models.OneToOneField("core.Order", on_delete=models.PROTECT,
                                 related_name="tron_gateway_invoice")
    payment_intent = models.OneToOneField(
        "core.PaymentIntent", on_delete=models.PROTECT,
        related_name="tron_gateway_invoice")
    buyer_email = models.EmailField(max_length=254)
    source_host = models.CharField(max_length=150)
    language = models.CharField(max_length=2)
    receiver = models.CharField(max_length=34)
    amount_sun = models.BigIntegerField()
    issued_ms = models.BigIntegerField()
    expires_ms = models.BigIntegerField()
    claim_sha256 = models.CharField(max_length=64, unique=True)
    quote_fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=24, default="email_pending")
    txid = models.CharField(max_length=64, unique=True, null=True, blank=True)
    proof_digest = models.CharField(max_length=64, blank=True, default="")
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Deliberately never recycle an exact native TRX amount at this address:
        # old/late transfers cannot be attributed to a new buyer.
        constraints = [
            models.UniqueConstraint(fields=["receiver", "amount_sun"],
                                    name="tron_gateway_unique_quote_amount")
        ]
        indexes = [models.Index(fields=["status", "created_at"],
                                name="tron_gateway_status_created")]

    def __str__(self):
        return f"TRON invoice {self.pk}: {self.status}"

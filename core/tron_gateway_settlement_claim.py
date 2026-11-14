"""Single native-TRON mainnet transaction claim for the NEW gateway writer.

The primary key prevents two *participating* payment writers claiming one
canonical transaction. A legacy writer bypassing this model is NOT protected.
"""
from django.db import models
from django.db.models.deletion import PROTECT


class TronMainnetSettlementClaim(models.Model):
    # The TRON mainnet hash is unique across new merchant invoices/providers.
    txid = models.CharField(max_length=64, primary_key=True)
    provider = models.CharField(max_length=50)
    invoice = models.OneToOneField(
        "core.TronGatewayInvoice", on_delete=PROTECT,
        related_name="settlement_claim",
    )
    payment_intent = models.OneToOneField(
        "core.PaymentIntent", on_delete=PROTECT,
        related_name="tron_mainnet_settlement_claim",
    )
    proof_digest = models.CharField(max_length=64)
    claimed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "TRON mainnet settlement claim"

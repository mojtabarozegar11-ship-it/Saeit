"""Persisted real MOJ-PROP-01 native TRX orders, settlement and delivery records.

No wallet private key, payout or live broker trading is stored/implemented here.
Only an operator-authorized, independent foreign merchant checkout may issue an
invoice, and payment receipts must be attributed by a globally unique TXID.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class PropV141NativeOrder(models.Model):
    """One immutable buyer-signed assessment invoice, not a job application."""
    reference = models.CharField(max_length=56, unique=True)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="mojprop_v141_native_orders",
    )
    product_code = models.CharField(max_length=20, default="MOJ-PROP-01")
    country_of_residence = models.CharField(max_length=2)
    recipient = models.CharField(max_length=34)
    payer_hex41 = models.CharField(max_length=42)
    amount_sun = models.PositiveBigIntegerField(default=30_000_000)
    terms_version = models.CharField(max_length=96)
    terms_sha256 = models.CharField(max_length=64)
    consent_digest = models.CharField(max_length=64)
    payer_wallet_attestation_sha256 = models.CharField(max_length=64)
    legal_clearance_digest = models.CharField(max_length=64)
    clearance_document_ref = models.CharField(max_length=128)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(
        max_length=18, choices=(("issued", "Issued"), ("settled", "Settled")),
        default="issued",
    )
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=("buyer", "-created_at"), name="mp_v141_pay_buyer"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_sun=30_000_000), name="mp_v141_pay_30m_sun",
            ),
            models.CheckConstraint(
                condition=Q(product_code="MOJ-PROP-01"),
                name="mp_v141_pay_correct_sku",
            ),
        ]


class PropGlobalTRXSettlement(models.Model):
    """Universal TXID reservation for all NEW MojPlayWin/Prop TRX products.

    Other legacy payment SKUs must be reconciled/migrated into this table before
    they are allowed to share the same receiving wallet and become payable.
    """
    network = models.CharField(max_length=24, default="tron-mainnet")
    txid = models.CharField(max_length=64)
    product_code = models.CharField(max_length=32)
    order_reference = models.CharField(max_length=96, unique=True)
    evidence_sha256 = models.CharField(max_length=64)
    solidified_block = models.PositiveBigIntegerField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("network", "txid"), name="mp_global_trx_txid_unique",
            ),
            models.CheckConstraint(
                condition=Q(solidified_block__gt=0),
                name="mp_global_trx_block_positive",
            ),
        ]


class PropV141NativeReceipt(models.Model):
    """One settled order -> one private simulated account and virtual book."""
    order = models.OneToOneField(
        PropV141NativeOrder, on_delete=models.PROTECT,
        related_name="native_receipt",
    )
    settlement = models.OneToOneField(
        PropGlobalTRXSettlement, on_delete=models.PROTECT,
        related_name="mojprop_plan1_native_receipt",
    )
    state = models.OneToOneField(
        "prop_firm.PropV141SimState", on_delete=models.PROTECT,
        related_name="native_paid_receipt",
    )
    book = models.OneToOneField(
        "prop_firm.PropV141VirtualBook", on_delete=models.PROTECT,
        related_name="native_paid_receipt",
    )
    confirmed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

# Separately versioned native TRX merchant orders and atomic DEMO delivery.
from .plan1_v141_native_payment_models import (  # noqa: E402,F401
    PropV141NativeOrder, PropGlobalTRXSettlement, PropV141NativeReceipt,
)

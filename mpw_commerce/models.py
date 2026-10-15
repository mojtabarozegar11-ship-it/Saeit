"""Order-level, provider-independent payment and fulfillment evidence.

No web routes or cron are enabled by including these models. The receiving
wallet is never asked to approve an order or sign a spending transaction.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class CommerceInvoice(models.Model):
    class Status(models.TextChoices):
        AWAITING = "awaiting", "Awaiting blockchain verification"
        PAID = "paid", "Verified payment"
        EXPIRED = "expired", "Expired"
        REVIEW = "review", "Review required"

    order = models.OneToOneField(
        "core.Order", on_delete=models.PROTECT,
        related_name="mpw_commerce_invoice",
    )
    asset = models.CharField(max_length=3, choices=[("ETH","ETH"),("TRX","TRX")])
    network = models.CharField(max_length=32)
    recipient = models.CharField(max_length=100)
    expected_sender = models.CharField(max_length=100)
    amount_atomic = models.CharField(max_length=50)
    total_usd = models.DecimalField(max_digits=14, decimal_places=2)
    quote_usd_per_asset = models.DecimalField(max_digits=30, decimal_places=12)
    quote_source = models.CharField(max_length=32)
    quote_observed_at = models.DateTimeField()
    sender_challenge_id = models.CharField(max_length=128)
    sender_signature_verified_at = models.DateTimeField()
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.AWAITING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["network","recipient","amount_atomic"],
                name="mpw_commerce_unique_native_amount",
            ),
            models.CheckConstraint(
                condition=Q(total_usd__gt=0),
                name="mpw_commerce_positive_usd",
            ),
        ]


class CommerceReceipt(models.Model):
    """Persist only an independently verified, finalized blockchain receipt."""
    invoice = models.OneToOneField(
        CommerceInvoice, on_delete=models.PROTECT,
        related_name="payment_receipt",
    )
    network = models.CharField(max_length=32)
    tx_hash = models.CharField(max_length=80)
    sender = models.CharField(max_length=100)
    recipient = models.CharField(max_length=100)
    amount_atomic = models.CharField(max_length=50)
    evidence_digest = models.CharField(max_length=64)
    backend = models.CharField(max_length=64)
    finalized_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["network","tx_hash"],
                name="mpw_commerce_unique_verified_tx",
            ),
        ]


class CommerceFulfillment(models.Model):
    """Durable, one-item-one-grant fulfillment outbox.

    'ready' is a buyer entitlement, NOT an exposed PDF URL.
    Service and subscription activations require separate idempotent adapters.
    Physical shipping requires a carrier/warehouse dispatch integration.
    """
    class Kind(models.TextChoices):
        DIGITAL = "digital", "Digital download"
        SUBSCRIPTION = "subscription", "Subscription"
        SERVICE = "service", "Service"
        PHYSICAL = "physical", "Physical goods"

    class Status(models.TextChoices):
        READY = "ready", "Digital entitlement ready"
        QUEUED = "queued", "Activation queued"
        DISPATCH = "awaiting_dispatch", "Shipment awaiting dispatch"
        COMPLETE = "complete", "Delivered"
        FAILED = "failed", "Retry required"

    item = models.OneToOneField(
        "core.OrderItem", on_delete=models.PROTECT,
        related_name="mpw_fulfillment",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=24, choices=Status.choices)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"],name="mpw_fulfill_status_idx"),
        ]


class BuyerWalletChallenge(models.Model):
    """Short-lived one-time wallet-link authorization for an authenticated buyer.

    This is a signed message only. It never authorizes fund transfers, spending
    allowances, merchant operations or order settlement.
    """
    order = models.ForeignKey(
        "core.Order", on_delete=models.PROTECT,related_name="wallet_link_challenges",
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="mpw_wallet_link_challenges",
    )
    asset = models.CharField(
        max_length=3, choices=[("ETH","ETH"),("TRX","TRX")],
    )
    sender_address = models.CharField(max_length=100)
    nonce = models.CharField(max_length=64,unique=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True,blank=True)
    used_at = models.DateTimeField(null=True,blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class CommerceOrderRequest(models.Model):
    """Buyer-created cart with one UUID idempotency key and at most one order.

    This cannot mark an order paid; all coins use separate verified invoices.
    """
    idempotency_key = models.UUIDField(unique=True)
    requested_product_id = models.PositiveBigIntegerField()
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="mpw_cart_requests",
    )
    order = models.OneToOneField(
        "core.Order", null=True, blank=True,
        on_delete=models.PROTECT, related_name="mpw_cart_request",
    )
    asset = models.CharField(
        max_length=3, choices=[("ETH", "ETH"), ("TRX", "TRX")],
    )
    created_at = models.DateTimeField(auto_now_add=True)

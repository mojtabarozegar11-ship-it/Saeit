"""MojPlayWin-only native-asset offers and immutable checkout quotations."""
import uuid
from django.core.validators import MinValueValidator
from django.db import models
from .models import T


class MojCryptoOffer(T):
    """Price explicitly set by the merchant in smallest on-chain units."""
    product = models.ForeignKey("core.Product", on_delete=models.PROTECT, related_name="moj_crypto_offers")
    asset = models.CharField(max_length=3, choices=[("ETH", "ETH (Ethereum)"), ("TRX", "TRX (TRON)")])
    atomic_amount = models.DecimalField(max_digits=40, decimal_places=0, validators=[MinValueValidator(1)])
    active = models.BooleanField(default=False)
    # Files live OUTSIDE any served webroot; this is an optional relative path inside the private folder.
    private_file = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "asset"], name="moj_crypto_offer_product_asset")]

    def __str__(self):
        return f"{self.product_id}: {self.asset}"


class MojCryptoInvoice(T):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order = models.OneToOneField("core.Order", on_delete=models.PROTECT, related_name="moj_crypto_invoice")
    offer = models.ForeignKey(MojCryptoOffer, on_delete=models.PROTECT, related_name="invoices")
    asset = models.CharField(max_length=3)
    atomic_amount = models.DecimalField(max_digits=40, decimal_places=0)
    merchant_address = models.CharField(max_length=100)
    status = models.CharField(max_length=24, default="awaiting_payment")
    tx_hash = models.CharField(max_length=66, null=True, blank=True, unique=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    confirmed_block = models.BigIntegerField(null=True, blank=True)
    last_error = models.CharField(max_length=250, blank=True, default="")

    def __str__(self):
        return f"MojPlayWin #{self.order_id} ({self.asset})"

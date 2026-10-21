"""Isolated merchant-scoped objects, not mounted into the live site.

All product assets are private and addressed by a server-generated hex file key,
not an HTTP filename.  No wallets, private signing keys or payouts are stored.
"""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class Merchant(models.Model):
    id = models.BigAutoField(primary_key=True)
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending vetting'
        APPROVED = 'approved', 'Approved'
        SUSPENDED = 'suspended', 'Suspended'

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name='moj_merchants')
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)


class MerchantAddress(models.Model):
    id = models.BigAutoField(primary_key=True)
    """Address ownership must be proved OFFLINE/independently before verified_at is set.

    One address cannot be given to two merchants nor reused across pilot orders.
    """
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='addresses')
    address = models.CharField(max_length=64, unique=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DigitalProduct(models.Model):
    id = models.BigAutoField(primary_key=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='digital_products')
    sku = models.CharField(max_length=48)
    title = models.CharField(max_length=180)
    price_usd = models.DecimalField(max_digits=11, decimal_places=2)
    file_key = models.CharField(max_length=32, unique=True)
    sha256 = models.CharField(max_length=64)
    download_name = models.CharField(max_length=96, default='product.zip')
    active = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['merchant', 'sku'], name='moj_unique_seller_sku'),
            models.CheckConstraint(condition=Q(price_usd__gt=0), name='moj_product_positive_usd'),
        ]


class Purchase(models.Model):
    id = models.BigAutoField(primary_key=True)
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending verified payment'
        DELIVERED = 'delivered', 'Verified and delivered'

    reference = models.CharField(max_length=80, unique=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='purchases')
    product = models.ForeignKey(DigitalProduct, on_delete=models.PROTECT, related_name='purchases')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name='moj_purchases')
    destination = models.OneToOneField(MerchantAddress, on_delete=models.PROTECT,
                                       related_name='purchase')
    usd_amount = models.DecimalField(max_digits=11, decimal_places=2)
    amount_sun = models.BigIntegerField()
    network = models.CharField(max_length=16, default='tron-mainnet')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    confirmed_txid = models.CharField(max_length=64, unique=True, null=True, blank=True)
    fulfillment_event_id = models.CharField(max_length=72, unique=True, null=True, blank=True)
    delivery_id = models.UUIDField(null=True, blank=True, unique=True)

    class Meta:
        indexes = [models.Index(fields=['merchant', 'status'], name='moj_seller_status_idx')]
        constraints = [
            models.CheckConstraint(condition=Q(amount_sun__gt=0), name='moj_order_positive_sun'),
            models.CheckConstraint(condition=Q(usd_amount__gt=0), name='moj_order_positive_usd'),
        ]


class Entitlement(models.Model):
    id = models.BigAutoField(primary_key=True)
    purchase = models.OneToOneField(Purchase, on_delete=models.PROTECT, related_name='entitlement')
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    max_downloads = models.PositiveSmallIntegerField(default=5)
    downloads = models.PositiveSmallIntegerField(default=0)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(max_downloads__gte=1) & Q(max_downloads__lte=20), name='moj_download_limit'),
        ]
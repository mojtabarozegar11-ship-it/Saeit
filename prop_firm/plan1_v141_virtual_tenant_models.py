"""Prospective v1.4.1 per-user VIRTUAL fill persistence only.

These tables are independent of historical v1.2 funded brokerage-account
allocations, and do NOT contain broker credentials, wallets, payment evidence,
or an ability to place orders. 0010 must never run on production until its
full MariaDB migration/restore/concurrency rehearsal is independently proven.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class PropV141VirtualBook(models.Model):
    state = models.OneToOneField(
        "prop_firm.PropV141SimState", on_delete=models.PROTECT,
        related_name="private_virtual_trade_book",
    )
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,
                              on_delete=models.PROTECT,
                              related_name="mojprop_v141_virtual_books")
    trader_ref = models.CharField(max_length=96)
    terms_sha256 = models.CharField(max_length=64)
    trusted_feed_source = models.CharField(max_length=160)
    evaluation_started_at = models.DateTimeField()
    max_unlocked_stage = models.PositiveSmallIntegerField(default=1)
    last_sequence = models.PositiveBigIntegerField(default=0)
    last_history_sha256 = models.CharField(max_length=64, blank=True)
    last_realized_net_usd = models.DecimalField(
        max_digits=24, decimal_places=8, default=0)
    last_fully_closed_count = models.PositiveBigIntegerField(default=0)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(
            fields=["owner", "-opened_at"], name="mp_v141_virtual_owner"
        )]
        constraints = [
            models.CheckConstraint(
                condition=Q(max_unlocked_stage__gte=1)
                & Q(max_unlocked_stage__lte=2),
                name="mp_v141_virt_stage_range",
            ),
            models.CheckConstraint(
                condition=Q(last_sequence__gte=0),
                name="mp_v141_virt_seq_nonneg",
            ),
        ]


class PropV141VirtualFill(models.Model):
    book = models.ForeignKey(
        PropV141VirtualBook, on_delete=models.PROTECT,
        related_name="virtual_fills",
    )
    sequence = models.PositiveBigIntegerField()
    # Server-assigned source event ID is unique across ALL customer books.
    event_id = models.CharField(max_length=96, unique=True)
    position_ref = models.CharField(max_length=96)
    stage = models.PositiveSmallIntegerField()
    action = models.CharField(max_length=5)
    direction = models.CharField(max_length=4)
    symbol = models.CharField(max_length=10)
    quantity_ounces = models.DecimalField(max_digits=15, decimal_places=4)
    price_usd_per_ounce = models.DecimalField(max_digits=18, decimal_places=4)
    fee_usd = models.DecimalField(max_digits=16, decimal_places=4)
    executed_at_utc = models.DateTimeField()
    feed_source = models.CharField(max_length=160)
    raw_event_sha256 = models.CharField(max_length=64)
    stored_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["book_id", "sequence"]
        indexes = [models.Index(
            fields=["book", "-stored_at"], name="mp_v141_virt_recent"
        )]
        constraints = [
            models.UniqueConstraint(
                fields=["book", "sequence"], name="mp_v141_virt_book_seq"
            ),
            models.CheckConstraint(
                condition=Q(sequence__gte=1),
                name="mp_v141_virt_event_seq_pos",
            ),
            models.CheckConstraint(
                condition=Q(stage__gte=1) & Q(stage__lte=2),
                name="mp_v141_virt_event_stage",
            ),
            models.CheckConstraint(
                condition=Q(quantity_ounces__gt=0),
                name="mp_v141_virt_positive_qty",
            ),
            models.CheckConstraint(
                condition=Q(price_usd_per_ounce__gt=0),
                name="mp_v141_virt_positive_price",
            ),
            models.CheckConstraint(
                condition=Q(fee_usd__gte=0),
                name="mp_v141_virt_nonneg_fee",
            ),
        ]

"""MojPlayWin-only internal opportunity and manufacturing-brief ledger.

Not a customer Order, payment, product, fulfillment instruction or VPS queue.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class MojPlayWinOpportunitySignal(models.Model):
    """One unique main-site content card; not evidence of customer demand."""

    SITE = "mojplaywin.com"
    SOURCE_KINDS = (
        ("venture", "Venture card"),
        ("section", "Activity section card"),
        ("feature", "Main feature card"),
    )
    source_key = models.CharField(max_length=130, unique=True)
    source_site = models.CharField(max_length=60, default=SITE, editable=False)
    source_kind = models.CharField(max_length=12, choices=SOURCE_KINDS)
    source_path = models.CharField(max_length=255, blank=True)
    card_title = models.CharField(max_length=300)
    card_description = models.TextField()
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("source_key",)
        verbose_name = "MojPlayWin activity signal"
        verbose_name_plural = "MojPlayWin activity signals"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_site="mojplaywin.com"),
                name="mpw_signal_site_only",
            ),
        ]

    def __str__(self):
        return self.card_title


class MojPlayWinManufacturingOrder(models.Model):
    """Internal proposed production work, never a customer's commercial order.

    Later phases must implement a separate approval and factory-dispatch gate.
    Nothing here can reach a storefront.
    """

    STATUSES = (
        ("proposed_for_review", "Proposed — review required"),
        ("scoped", "Scoped — not approved for execution"),
        ("rejected", "Rejected or deferred"),
    )
    proposal_id = models.CharField(max_length=30, unique=True)
    signal = models.OneToOneField(
        MojPlayWinOpportunitySignal,
        on_delete=models.PROTECT,
        related_name="manufacturing_brief",
    )
    product_title = models.CharField(max_length=300)
    file_format = models.CharField(max_length=35)
    deliverable = models.TextField()
    priority_hypothesis = models.PositiveSmallIntegerField(default=3)
    status = models.CharField(
        max_length=30,
        choices=STATUSES,
        default="proposed_for_review",
        db_index=True,
    )
    proposed_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="mojplaywin_manufacturing_briefs",
    )
    review_note = models.TextField(blank=True)
    demand_verified = models.BooleanField(default=False)
    rights_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-priority_hypothesis", "proposal_id")
        verbose_name = "MojPlayWin internal manufacturing brief"
        verbose_name_plural = "MojPlayWin internal manufacturing briefs"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(priority_hypothesis__gte=1, priority_hypothesis__lte=5),
                name="mpw_brief_priority_1_5",
            ),
        ]

    def clean(self):
        super().clean()
        if self.signal_id and self.signal.source_site != MojPlayWinOpportunitySignal.SITE:
            raise ValidationError({"signal": "Only MojPlayWin main-site signals are permitted."})
        if self.status == "scoped" and (not self.proposed_owner_id or not self.review_note.strip()):
            raise ValidationError("Scoping requires a responsible owner and review note.")
        if self.status not in dict(self.STATUSES):
            raise ValidationError({"status": "Unknown internal brief status."})

    def __str__(self):
        return self.product_title

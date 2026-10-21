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
    ORDER_ORIGINS = (
        ("site", "Site activity and cards"),
        ("customer", "Genuine customer production request"),
        ("market", "Independent market demand"),
        ("invention", "Factory-originated invention or R&D"),
    )
    STAGES = (
        ("not_started", "Not sent to production"),
        ("manufacturing", "Production in progress (operator-recorded)"),
        ("qa_review", "Awaiting independent quality review"),
        ("rework_required", "Quality failed — correction order open"),
        ("rework_in_progress", "Correction in progress"),
        ("attention_required", "Escalated expert correction, never discarded"),
        ("qa_passed", "Quality passed — not approved for sale"),
    )
    proposal_id = models.CharField(max_length=30, unique=True, blank=True)
    origin_type = models.CharField(max_length=12, choices=ORDER_ORIGINS, default="site", db_index=True)
    origin_reference = models.CharField(max_length=180, unique=True, blank=True, null=True)
    origin_description = models.TextField(blank=True)
    production_stage = models.CharField(max_length=25, choices=STAGES, default="not_started", db_index=True)
    quality_round = models.PositiveIntegerField(default=0)
    signal = models.OneToOneField(
        MojPlayWinOpportunitySignal,
        on_delete=models.PROTECT,
        related_name="manufacturing_brief",
        null=True,
        blank=True,
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
            models.CheckConstraint(
                condition=(
                    models.Q(origin_type="site", signal__isnull=False)
                    | models.Q(origin_type__in=("customer", "market", "invention"), signal__isnull=True)
                ),
                name="mpw_order_origin_signal_boundary",
            ),
        ]

    def clean(self):
        super().clean()
        if self.origin_type == "site":
            if not self.signal_id:
                raise ValidationError({"signal": "Site-origin work requires an actual MojPlayWin card."})
            if self.signal.source_site != MojPlayWinOpportunitySignal.SITE:
                raise ValidationError({"signal": "Only MojPlayWin main-site cards are permitted."})
        elif self.origin_type in ("customer", "market", "invention"):
            if self.signal_id:
                raise ValidationError({"signal": "Non-site production needs its independent origin evidence."})
            if not self.origin_reference or not self.origin_reference.strip():
                raise ValidationError({"origin_reference": "An external unique request/reference is required."})
            if not self.origin_description.strip():
                raise ValidationError({"origin_description": "Describe actual origin and evidence; never invent demand."})
        else:
            raise ValidationError({"origin_type": "Unknown production origin."})
        if self.production_stage != "not_started" and self.status == "rejected":
            raise ValidationError({"status": "A produced item cannot be discarded for quality failure."})
        if self.status == "scoped" and (not self.proposed_owner_id or not self.review_note.strip()):
            raise ValidationError("Scoping requires a responsible owner and review note.")
        if self.status not in dict(self.STATUSES):
            raise ValidationError({"status": "Unknown internal brief status."})

    def __str__(self):
        return self.product_title


class MojPlayWinQAReview(models.Model):
    """One immutable verdict on a specific version; failure creates rework."""
    VERDICTS = (("pass", "Verified pass"), ("fail", "Failed — repair required"))
    brief = models.ForeignKey(
        MojPlayWinManufacturingOrder, related_name="quality_reviews", on_delete=models.PROTECT
    )
    review_key = models.CharField(max_length=130, unique=True)
    round_number = models.PositiveIntegerField()
    verdict = models.CharField(max_length=8, choices=VERDICTS)
    artifact_reference = models.CharField(max_length=255)
    summary = models.TextField()
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("brief", "round_number"), name="mpw_qa_unique_round"
            ),
        ]


class MojPlayWinQADefect(models.Model):
    """Actionable root-cause evidence; a failed review cannot be silently closed."""
    SEVERITIES = (
        ("critical", "Critical"),
        ("major", "Major"),
        ("minor", "Minor"),
    )
    review = models.ForeignKey(
        MojPlayWinQAReview, related_name="defects", on_delete=models.PROTECT
    )
    defect_code = models.CharField(max_length=70)
    severity = models.CharField(max_length=10, choices=SEVERITIES)
    cause = models.TextField()
    expected = models.TextField()
    actual = models.TextField()
    correction_plan = models.TextField()
    resolution_evidence = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("review", "defect_code"), name="mpw_defect_unique_code_per_review"
            ),
        ]


class MojPlayWinReworkCycle(models.Model):
    """Durable return-to-production ticket, never a cancellation of the product."""
    STATES = (
        ("queued", "Awaiting corrective production"),
        ("in_progress", "Corrective production in progress"),
        ("needs_expert", "Expert intervention required"),
        ("ready_for_retest", "Fix evidence submitted; independent retest required"),
    )
    failed_review = models.OneToOneField(
        MojPlayWinQAReview, related_name="rework_cycle", on_delete=models.PROTECT
    )
    brief = models.ForeignKey(
        MojPlayWinManufacturingOrder, related_name="rework_cycles", on_delete=models.PROTECT
    )
    attempt_number = models.PositiveIntegerField()
    state = models.CharField(max_length=20, choices=STATES, default="queued")
    instructions = models.TextField()
    replacement_artifact_reference = models.CharField(max_length=255, blank=True)
    fix_summary = models.TextField(blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

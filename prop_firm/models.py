"""Persistence for Moj Prop, a MojPlayWin division; no brokerage/payment integrations.

Database rows represent evidence references, NOT authority to move capital.
No public write endpoints are supplied. All funding, payout and live trading remain off.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .rules import LEVELS, POLICY


class PropTrader(models.Model):
    """Profile linked to an existing Django identity; no public signup."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="moj_prop_trader")
    preferred_language = models.CharField(max_length=8, default="en")
    kyc_status = models.CharField(
        max_length=16, default="not_started",
        choices=[("not_started", "Not started"), ("pending", "Pending review"),
                 ("verified", "Verified"), ("rejected", "Rejected")],
    )
    eligibility_status = models.CharField(
        max_length=16, default="not_reviewed",
        choices=[("not_reviewed", "Not reviewed"), ("eligible", "Eligible"),
                 ("blocked", "Blocked")],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Moj Prop profile #{self.pk}"


class PropAccount(models.Model):
    """One simulated challenge phase or funded-tier ledger compartment."""
    class Kind(models.TextChoices):
        PHASE_ONE = "phase_one", "Challenge stage one (simulation)"
        PHASE_TWO = "phase_two", "Challenge stage two (simulation)"
        FUNDED = "funded", "Company-funded real brokerage"

    class Status(models.TextChoices):
        WAITING = "waiting", "Awaiting evidence"
        ACTIVE = "active", "Reconciliation in progress"
        PASSED = "passed", "Assessment passed"
        BREACHED = "breached", "Risk breach"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trader = models.ForeignKey(PropTrader, on_delete=models.PROTECT,
                               related_name="accounts")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.WAITING)
    tier_index = models.PositiveSmallIntegerField(default=0)
    starting_capital_usd = models.DecimalField(max_digits=18, decimal_places=2,
                                               default=Decimal("100.00"))
    reference = models.CharField(max_length=96, blank=True)
    policy_version = models.CharField(max_length=32, default=POLICY.version)
    reconciled_by_operator = models.BooleanField(default=False)
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["trader", "-created_at"], name="mp_account_trader_created"),
            models.Index(fields=["kind", "status"], name="mp_account_type_status"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(tier_index__gte=0) & Q(tier_index__lte=13),
                name="mp_tier_range_0_13",
            ),
            models.CheckConstraint(
                condition=Q(starting_capital_usd__gt=0),
                name="mp_initial_capital_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.tier_index, int) or not 0 <= self.tier_index < len(LEVELS):
            raise ValidationError({"tier_index": "Invalid capital tier"})
        if self.kind == self.Kind.FUNDED:
            if self.starting_capital_usd != LEVELS[self.tier_index]:
                raise ValidationError({"starting_capital_usd": "Must match the funded tier"})
            if not self.reference:
                raise ValidationError({"reference": "Broker reference required for funded accounts"})
        else:
            if self.tier_index != 0:
                raise ValidationError({"tier_index": "Simulated evaluation has no funded tier"})
            if self.starting_capital_usd != Decimal("100"):
                raise ValidationError({"starting_capital_usd": "Simulation assessment uses a $100 baseline"})

    def save(self, *args, **kwargs):
        # The ORM save path must not bypass tier consistency.
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.kind} / {self.id}"


class PropExecution(models.Model):
    """Externally sourced execution record; never accepted from customer HTTP."""
    account = models.ForeignKey(PropAccount, on_delete=models.PROTECT,
                                related_name="executions")
    external_event_id = models.CharField(max_length=160)
    data_source = models.CharField(max_length=64)
    symbol = models.CharField(max_length=32)
    closed_at = models.DateTimeField(db_index=True)
    gross_realized_usd = models.DecimalField(max_digits=18, decimal_places=4)
    total_fees_usd = models.DecimalField(max_digits=18, decimal_places=4,
                                        default=Decimal("0"))
    reconciliation_status = models.CharField(
        max_length=12, choices=[
            ("pending", "Pending"), ("verified", "Verified"), ("rejected", "Rejected")
        ], default="pending")
    evidence_digest = models.CharField(max_length=64, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-closed_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["account", "external_event_id"],
                                    name="mp_execution_external_unique"),
            models.CheckConstraint(condition=Q(total_fees_usd__gte=0),
                                   name="mp_execution_fees_nonnegative"),
        ]
        indexes = [models.Index(fields=["account", "closed_at"], name="mp_trade_account_closed")]

    @property
    def net_realized_usd(self):
        return self.gross_realized_usd - self.total_fees_usd

    def __str__(self):
        return f"execution:{self.account_id}:{self.external_event_id}"


class PropEquityObservation(models.Model):
    """Broker/simulation mark-to-market evidence. No client-controlled values."""
    account = models.ForeignKey(PropAccount, on_delete=models.PROTECT,
                                related_name="equity_observations")
    external_event_id = models.CharField(max_length=160)
    observed_at = models.DateTimeField(db_index=True)
    equity_usd = models.DecimalField(max_digits=18, decimal_places=4)
    is_session_open = models.BooleanField(default=False)
    reconciliation_status = models.CharField(
        max_length=12, choices=[
            ("pending", "Pending"), ("verified", "Verified"), ("rejected", "Rejected")
        ], default="pending")
    evidence_digest = models.CharField(max_length=64, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-observed_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["account", "external_event_id"],
                                    name="mp_equity_event_unique"),
            models.CheckConstraint(condition=Q(equity_usd__gte=0),
                                   name="mp_equity_nonnegative"),
        ]
        indexes = [models.Index(fields=["account", "-observed_at"],
                                name="mp_equity_account_recent")]

    def __str__(self):
        return f"equity:{self.account_id}:{self.external_event_id}"


class PropDecisionLog(models.Model):
    """Recorded calculation result; this is NOT an approved transfer instruction."""
    account = models.ForeignKey(PropAccount, on_delete=models.PROTECT,
                                related_name="decision_logs")
    decision_key = models.CharField(max_length=96)
    category = models.CharField(max_length=20, choices=[
        ("challenge", "Challenge"), ("promotion", "Promotion"),
        ("payout_preview", "Payout estimate"), ("risk", "Risk assessment"),
    ])
    policy_version = models.CharField(max_length=32, default=POLICY.version)
    qualifies = models.BooleanField(default=False)
    reasons = models.JSONField(default=list)
    evidence_digest = models.CharField(max_length=64)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        constraints = [
            models.UniqueConstraint(fields=["account", "decision_key"],
                                    name="mp_decision_idempotency"),
        ]

    def __str__(self):
        return f"{self.category}:{self.decision_key}"



class PropProfitAllocation(models.Model):
    """Internal provisional 70/30 distribution, never a bank/wallet payment."""
    account = models.ForeignKey(PropAccount, on_delete=models.PROTECT,
                                related_name="profit_allocations")
    period_number = models.PositiveIntegerField()
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    cumulative_realized_net_usd = models.DecimalField(max_digits=18, decimal_places=4)
    previously_allocated_usd = models.DecimalField(max_digits=18, decimal_places=2)
    eligible_profit_usd = models.DecimalField(max_digits=18, decimal_places=2)
    trader_profit_usd = models.DecimalField(max_digits=18, decimal_places=2)
    company_profit_usd = models.DecimalField(max_digits=18, decimal_places=2)
    evidence_digest = models.CharField(max_length=64)
    policy_version = models.CharField(max_length=32, default=POLICY.version)
    status = models.CharField(max_length=16, default="provisional",
                              choices=[("provisional", "Provisional — not payable")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["account_id", "period_number"]
        constraints = [
            models.UniqueConstraint(fields=["account", "period_number"],
                                    name="mp_profit_account_period_unique"),
            models.CheckConstraint(
                condition=Q(period_number__gte=1),
                name="mp_profit_period_positive",
            ),
            models.CheckConstraint(
                condition=Q(previously_allocated_usd__gte=0),
                name="mp_profit_previous_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(eligible_profit_usd__gte=0),
                name="mp_profit_eligible_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(trader_profit_usd__gte=0),
                name="mp_profit_trader_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(company_profit_usd__gte=0),
                name="mp_profit_company_nonnegative",
            ),
        ]

    def __str__(self):
        return f"provisional-profit:{self.account_id}:{self.period_number}"


class PropProfitJournalLine(models.Model):
    """Balanced provisional memo entries, not a general ledger or cash asset."""
    allocation = models.ForeignKey(
        PropProfitAllocation, on_delete=models.PROTECT, related_name="journal_lines"
    )
    code = models.CharField(max_length=16, choices=[
        ("pool_debit", "Provisional pool debit"),
        ("trader_credit", "Trader share provisional credit"),
        ("company_credit", "Company share provisional credit"),
    ])
    side = models.CharField(max_length=6, choices=[
        ("debit", "Debit"), ("credit", "Credit"),
    ])
    amount_usd = models.DecimalField(max_digits=18, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["allocation", "code"],
                                    name="mp_profit_line_code_unique"),
            models.CheckConstraint(condition=Q(amount_usd__gt=0),
                                   name="mp_profit_line_positive"),
        ]

    def __str__(self):
        return f"provisional-line:{self.allocation_id}:{self.code}"



class PropSocialEvidence(models.Model):
    """Privately reviewed trader-authored posts, never an auto-publishing task.

    Data are challenge-specific, may not be displayed publicly, and cannot
    authorize payment/funding on their own. Only the evidence review service
    may create or approve them; the administrative UI is read-only.
    """
    class Platform(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"

    class Review(models.TextChoices):
        PENDING = "pending", "Pending independent review"
        VERIFIED = "verified", "Verified by independent operator"
        REJECTED = "rejected", "Rejected evidence"

    account = models.ForeignKey(
        PropAccount, on_delete=models.PROTECT, related_name="social_evidence"
    )
    platform = models.CharField(max_length=12, choices=Platform.choices)
    trading_day = models.DateField(db_index=True)
    post_url = models.URLField(max_length=512, unique=True)
    posted_at = models.DateTimeField()
    review_status = models.CharField(
        max_length=12, choices=Review.choices, default=Review.PENDING
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.PROTECT, related_name="moj_prop_reviewed_social_posts"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    author_verified = models.BooleanField(default=False)
    public_visible = models.BooleanField(default=False)
    disclosure_verified = models.BooleanField(default=False)
    content_compliant = models.BooleanField(default=False)
    date_verified = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("account_id", "trading_day", "platform")
        constraints = [
            models.UniqueConstraint(
                fields=("account", "trading_day", "platform"),
                name="mp_social_day_platform_unique",
            ),
            models.CheckConstraint(
                condition=~Q(review_status="verified") | (
                    Q(reviewed_by__isnull=False) & Q(reviewed_at__isnull=False)
                    & Q(author_verified=True) & Q(public_visible=True)
                    & Q(disclosure_verified=True) & Q(content_compliant=True)
                    & Q(date_verified=True)
                ),
                name="mp_social_verified_review_gate",
            ),
        ]

    def clean(self):
        super().clean()
        from .social_policy import utc_day, valid_platform_post_url
        if self.account_id:
            if self.account.kind not in (
                PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO,
            ):
                raise ValidationError("Only simulated challenge days require social proofs")
            if self.account.policy_version == "2026-11-14/v1.1":
                raise ValidationError("Legacy paid cohorts cannot be retroactively changed")
            if self.account.policy_version != POLICY.version:
                raise ValidationError("Unsupported social challenge policy version")
            if self.account.opened_at and self.posted_at and self.posted_at < self.account.opened_at:
                raise ValidationError("Social publication predates challenge opening")
            if self.account.trader_id and self.reviewed_by_id == self.account.trader.user_id:
                raise ValidationError("Traders cannot independently verify their own posts")
        if self.posted_at and self.trading_day and utc_day(self.posted_at) != self.trading_day:
            raise ValidationError("Post must match its corresponding UTC trading day")
        if not valid_platform_post_url(self.post_url, self.platform):
            raise ValidationError("Unsupported post URL; profile pages are not proof")
        if self.review_status == self.Review.VERIFIED:
            if (not self.reviewed_by_id or self.reviewed_at is None
                    or not all((
                        self.author_verified, self.public_visible,
                        self.disclosure_verified, self.content_compliant,
                        self.date_verified,
                    ))):
                raise ValidationError("Independent approval and all post disclosures required")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"social-review:{self.account_id}:{self.trading_day}:{self.platform}"

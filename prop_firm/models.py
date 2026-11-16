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
from .plans import DEFAULT_PLAN_CODE, plan_for_code


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
    challenge_enrollment = models.ForeignKey(
        "PropChallengeEnrollment", null=True, blank=True,
        on_delete=models.PROTECT, related_name="phase_accounts"
    )
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
            if self.challenge_enrollment_id is not None:
                enrollment = self.challenge_enrollment
                if self.trader_id != enrollment.trader_id:
                    raise ValidationError("Funded plan belongs to a different trader")
                if self.tier_index < plan_for_code(enrollment.plan_code).starting_tier_index:
                    raise ValidationError("Funded account cannot start below purchased plan")
            if self.starting_capital_usd != LEVELS[self.tier_index]:
                raise ValidationError({"starting_capital_usd": "Must match the funded tier"})
            if not self.reference:
                raise ValidationError({"reference": "Broker reference required for funded accounts"})
        else:
            # Historical and unpurchased accounts retain their $100 baseline.
            # New accounts must use their immutable purchased plan's tier.
            plan = None
            if self.challenge_enrollment_id is not None:
                enrollment = self.challenge_enrollment
                if self.trader_id != enrollment.trader_id:
                    raise ValidationError("The plan enrollment belongs to a different trader")
                if self.policy_version != enrollment.terms_version:
                    raise ValidationError("Account terms differ from buyer's contract")
                try:
                    plan = plan_for_code(enrollment.plan_code)
                except ValueError as exc:
                    raise ValidationError("Unknown purchased challenge plan") from exc
            required_index = plan.starting_tier_index if plan else 0
            required_capital = plan.starting_capital_usd if plan else LEVELS[0]
            if self.tier_index != required_index:
                raise ValidationError({"tier_index": "Challenge tier must match purchased plan"})
            if self.starting_capital_usd != required_capital:
                raise ValidationError({"starting_capital_usd": "Challenge capital must match purchased plan"})

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
    # The broker's stable POSITION/trade ID groups partial fills and
    # stops a single round-trip being counted as many separate executions.
    # Blank historical IDs are deliberately NOT credited toward 50 trades.
    external_position_id = models.CharField(max_length=160, blank=True)
    execution_origin = models.CharField(
        max_length=12,
        choices=[("unknown", "Unknown"), ("manual", "Manual"),
                 ("bot", "Trader's automated strategy")],
        default="unknown",
    )
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
    # Legacy rows deliberately default to unknown; never infer that a
    # SHA-shaped digest means the mark came from an approved broker.
    data_source = models.CharField(max_length=64, blank=True, default="")
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



class PropChallengeEnrollment(models.Model):
    """One independently confirmed purchase binding both simulated phases.

    Only a trusted private gateway adapter may create confirmed purchases.
    This is a read-only record, not a customer self-attestation or TRX invoice.
    """
    trader = models.ForeignKey(
        PropTrader, on_delete=models.PROTECT, related_name="challenge_enrollments"
    )
    verified_invoice_ref = models.CharField(max_length=96, unique=True)
    plan_code = models.CharField(max_length=16, default=DEFAULT_PLAN_CODE)
    confirmed_at = models.DateTimeField(db_index=True)
    settlement_verified = models.BooleanField(default=False)
    terms_version = models.CharField(max_length=32, default=POLICY.version)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        from .social_policy import NEW_CONTRACT_VERSION, aware_utc
        if self.terms_version != NEW_CONTRACT_VERSION:
            raise ValidationError("New enrollment uses pre-disclosed v1.2 contract")
        try:
            plan_for_code(self.plan_code)
        except ValueError as exc:
            raise ValidationError({"plan_code": "Unknown challenge plan"}) from exc
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "plan_code", "verified_invoice_ref", "confirmed_at", "trader_id",
                "settlement_verified", "terms_version",
            ).first()
            if previous and (
                previous["plan_code"] != self.plan_code
                or previous["verified_invoice_ref"] != self.verified_invoice_ref
                or previous["confirmed_at"] != self.confirmed_at
                or previous["trader_id"] != self.trader_id
                # The source-only ledger must not let a generic Model.save()
                # flip pending->paid or rewrite disclosed contract terms.
                # A real paid enrollment must be inserted once by the
                # independently reconciled private gateway adapter.
                or previous["settlement_verified"] != self.settlement_verified
                or previous["terms_version"] != self.terms_version
            ):
                raise ValidationError("Confirmed purchase, settlement and terms are immutable")
        if self.trader_id and self.trader.user.is_active is not True:
            raise ValidationError("Inactive buyer cannot enter a funded challenge")
        import re
        if (type(self.verified_invoice_ref) is not str
                or re.fullmatch(
                    r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}",
                    self.verified_invoice_ref,
                ) is None):
            raise ValidationError("Bounded canonical payment reference required")
        from django.utils import timezone as _django_timezone
        confirmed = aware_utc(self.confirmed_at, "confirmed_at")
        if confirmed > _django_timezone.now():
            raise ValidationError("Purchase confirmation cannot be dated in the future")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PropSocialEvidence(models.Model):
    """Exactly two original posts per verified purchase: one per platform."""
    class Platform(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"

    class Review(models.TextChoices):
        PENDING = "pending", "Pending independent review"
        VERIFIED = "verified", "Verified and visible for four weeks"
        REJECTED = "rejected", "Rejected evidence"

    account = models.ForeignKey(
        PropAccount, on_delete=models.PROTECT, related_name="social_evidence"
    )
    enrollment = models.ForeignKey(
        PropChallengeEnrollment, null=True, blank=True,
        on_delete=models.PROTECT, related_name="social_posts"
    )
    platform = models.CharField(max_length=12, choices=Platform.choices)
    trading_day = models.DateField(null=True, blank=True)  # old draft metadata retained
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
    continued_visibility_verified = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("enrollment_id", "platform")
        constraints = [
            models.UniqueConstraint(
                fields=("enrollment", "platform"),
                name="mp_social_enrollment_platform_unique",
            ),
            models.CheckConstraint(
                condition=~Q(review_status="verified") | (
                    Q(reviewed_by__isnull=False) & Q(reviewed_at__isnull=False)
                    & Q(author_verified=True) & Q(public_visible=True)
                    & Q(disclosure_verified=True) & Q(content_compliant=True)
                    & Q(date_verified=True) & Q(continued_visibility_verified=True)
                ),
                name="mp_social_verified_review_gate",
            ),
        ]

    def clean(self):
        super().clean()
        from datetime import timedelta
        from .social_policy import (
            NEW_CONTRACT_VERSION, DURATION_DAYS, POST_START_GRACE_HOURS,
            aware_utc, valid_platform_post_url,
        )
        if not self.account_id or not self.enrollment_id:
            raise ValidationError("Verified purchase and challenge account required")
        if self.account.kind not in (
            PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO
        ):
            raise ValidationError("Social rule is only for simulated challenges")
        if (self.account.policy_version != NEW_CONTRACT_VERSION
                or self.enrollment.terms_version != NEW_CONTRACT_VERSION):
            raise ValidationError("Social rule only applies to prospective v1.2 enrollments")
        if (self.account.trader_id != self.enrollment.trader_id
                or self.account.challenge_enrollment_id != self.enrollment_id):
            raise ValidationError("Post must belong to this authenticated purchase")
        if not self.enrollment.settlement_verified:
            raise ValidationError("Independently settled purchase must be confirmed")
        if not valid_platform_post_url(self.post_url, self.platform):
            raise ValidationError("Unsupported post URL or banned profile")
        published = aware_utc(self.posted_at, "posted_at")
        start = aware_utc(self.enrollment.confirmed_at, "confirmed_at")
        from django.utils import timezone as _django_timezone
        if not start <= published <= start + timedelta(hours=POST_START_GRACE_HOURS):
            raise ValidationError("Post must be published within 24 hours of purchase")
        if published > _django_timezone.now():
            raise ValidationError("Future-dated social posts cannot be submitted")
        if self.review_status == self.Review.VERIFIED:
            from django.utils import timezone as _django_timezone
            reviewed = aware_utc(self.reviewed_at, "reviewed_at")
            if (reviewed < published + timedelta(days=DURATION_DAYS)
                    or reviewed > _django_timezone.now()
                    or not self.reviewed_by_id
                    or self.reviewed_by.is_staff is not True
                    or self.reviewed_by.is_active is not True
                    or self.reviewed_by_id == self.account.trader.user_id
                    or not all((
                        self.author_verified, self.public_visible,
                        self.disclosure_verified, self.content_compliant,
                        self.date_verified, self.continued_visibility_verified,
                    ))):
                raise ValidationError("28-day public lifetime and independent review required")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"social-review:{self.enrollment_id}:{self.platform}"

# Contact-only inquiries never imply TRX settlement or funded challenges.
from .lead_models import PropInterest

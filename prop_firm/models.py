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

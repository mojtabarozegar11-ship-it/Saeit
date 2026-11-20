"""Five isolated MOJ PROP simulation models.

These models deliberately contain no relation to auth_user, legacy prop_firm
models, shared commerce tables, or the factory database.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .simulation_policy import SIMULATION_POLICY


class PropSimulationIdentity(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        BLOCKED = "blocked", "Blocked"
        PENDING = "pending", "Pending verification"

    provider = models.CharField(max_length=32, default="email")
    subject_key = models.CharField(max_length=160)
    email_digest = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["provider", "subject_key"], name="mp_sim_identity_provider_subject"),
            models.UniqueConstraint(fields=["email_digest"], name="mp_sim_identity_email_digest"),
        ]
        indexes = [
            models.Index(fields=["provider", "subject_key"], name="mp_sim_identity_subject"),
            models.Index(fields=["status", "-created_at"], name="mp_sim_identity_status"),
        ]


class PropSimulationInvoiceOwner(models.Model):
    identity = models.ForeignKey(
        PropSimulationIdentity, on_delete=models.PROTECT, related_name="invoice_owners"
    )
    invoice_ref = models.CharField(max_length=96, unique=True)
    buyer_email_digest = models.CharField(max_length=64)
    settlement_reference = models.CharField(max_length=128, blank=True)
    settlement_verified = models.BooleanField(default=False)
    contract_version = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["identity", "-created_at"], name="mp_sim_owner_identity"),
            models.Index(fields=["settlement_verified", "-created_at"], name="mp_sim_owner_settled"),
        ]

    def clean(self):
        super().clean()
        if self.identity_id and self.buyer_email_digest != self.identity.email_digest:
            raise ValidationError("Invoice owner email identity does not match")
        if self.settlement_verified and not self.settlement_reference:
            raise ValidationError("Settled invoice owner requires settlement reference")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PropSimulationAccount(models.Model):
    class Kind(models.TextChoices):
        CHALLENGE = "challenge", "Challenge simulation"
        FUNDED_SIMULATION = "funded_simulation", "Funded-account simulation"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        PASSED = "passed", "Passed"
        BREACHED = "breached", "Breached"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.ForeignKey(
        PropSimulationIdentity, on_delete=models.PROTECT, related_name="simulation_accounts"
    )
    invoice_owner = models.ForeignKey(
        PropSimulationInvoiceOwner, on_delete=models.PROTECT, related_name="simulation_accounts"
    )
    account_ref = models.CharField(max_length=96, unique=True)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    starting_capital_usd = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("1000.00")
    )
    policy_version = models.CharField(max_length=32, default=SIMULATION_POLICY.contract_version)
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(starting_capital_usd__gt=0),
                name="mp_sim_account_capital_positive",
            )
        ]
        indexes = [
            models.Index(fields=["identity", "-created_at"], name="mp_sim_account_identity"),
            models.Index(fields=["kind", "status"], name="mp_sim_account_kind_status"),
        ]

    def clean(self):
        super().clean()
        if self.identity_id and self.invoice_owner_id:
            if self.identity_id != self.invoice_owner.identity_id:
                raise ValidationError("Simulation account identity does not match invoice owner")
        if self.invoice_owner_id and not self.invoice_owner.settlement_verified:
            raise ValidationError("Settled invoice owner required before simulation account")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PropSimulationLoginChallenge(models.Model):
    class Purpose(models.TextChoices):
        LOGIN = "login", "Login"
        RECOVERY = "recovery", "Recovery"

    identity = models.ForeignKey(
        PropSimulationIdentity, on_delete=models.PROTECT, related_name="login_challenges"
    )
    challenge_ref = models.CharField(max_length=96, unique=True)
    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    code_digest = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(attempt_count__gte=0),
                name="mp_sim_login_attempts_nonnegative",
            )
        ]
        indexes = [
            models.Index(fields=["identity", "-created_at"], name="mp_sim_login_identity"),
            models.Index(fields=["expires_at", "consumed_at"], name="mp_sim_login_expiry"),
        ]


class PropSimulationEvent(models.Model):
    class EventType(models.TextChoices):
        EQUITY = "equity", "Equity mark"
        EXECUTION = "execution", "Execution"
        RISK = "risk", "Risk observation"
        STATUS = "status", "Status transition"

    account = models.ForeignKey(
        PropSimulationAccount, on_delete=models.PROTECT, related_name="events"
    )
    event_ref = models.CharField(max_length=160)
    sequence_no = models.PositiveBigIntegerField()
    event_type = models.CharField(max_length=16, choices=EventType.choices)
    source = models.CharField(max_length=64)
    occurred_at = models.DateTimeField(db_index=True)
    payload_digest = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["account", "event_ref"], name="mp_sim_event_account_ref"),
            models.UniqueConstraint(fields=["account", "sequence_no"], name="mp_sim_event_account_sequence"),
        ]
        indexes = [
            models.Index(fields=["account", "-occurred_at"], name="mp_sim_event_account_time"),
            models.Index(fields=["event_type", "-created_at"], name="mp_sim_event_type_created"),
        ]


class PropSimulationPayment(models.Model):
    """Dedicated fixed-amount TRX payment ledger on the isolated MOJ PROP DB."""

    class Status(models.TextChoices):
        AWAITING = "awaiting", "Awaiting payment"
        PAID = "paid", "Paid"
        REVIEW = "review", "Manual review"
        EXPIRED = "expired", "Expired"

    invoice_owner = models.OneToOneField(
        PropSimulationInvoiceOwner,
        on_delete=models.PROTECT,
        related_name="payment",
    )
    payment_ref = models.CharField(max_length=96, unique=True)
    product = models.CharField(max_length=48, default="MOJPROP-STARTER30")
    network = models.CharField(max_length=32, default="tron-mainnet")
    recipient = models.CharField(max_length=64)
    amount_sun = models.PositiveBigIntegerField(default=30_000_000)
    payer_hex41 = models.CharField(max_length=42, null=True, blank=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    terms_acceptance_ref = models.CharField(max_length=128)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.AWAITING)
    txid = models.CharField(max_length=64, unique=True, null=True, blank=True)
    sender_hex41 = models.CharField(max_length=42, null=True, blank=True)
    solidified_block = models.PositiveBigIntegerField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_sun=30_000_000),
                name="mp_sim_payment_exact_30_trx",
            ),
            models.CheckConstraint(
                condition=Q(expires_at__gt=models.F("issued_at")),
                name="mp_sim_payment_expiry_after_issue",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="mp_sim_payment_status"),
            models.Index(fields=["payer_hex41", "status"], name="mp_sim_payment_payer"),
        ]

    def clean(self):
        super().clean()
        if self.amount_sun != 30_000_000:
            raise ValidationError("Starter30 payment must be exactly 30 TRX")
        if self.invoice_owner_id and self.invoice_owner.settlement_verified and self.status != self.Status.PAID:
            raise ValidationError("Settled owner requires paid payment status")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PropSimulationPayoutCommitment(models.Model):
    """Immutable 100% profit liability recorded after an independently verified pass."""

    class Status(models.TextChoices):
        PENDING_SETTLEMENT = "pending_settlement", "Pending treasury settlement"
        SETTLED = "settled", "Settled"
        BLOCKED = "blocked", "Blocked"
        DISPUTED = "disputed", "Disputed"

    account = models.OneToOneField(
        PropSimulationAccount,
        on_delete=models.PROTECT,
        related_name="payout_commitment",
    )
    realized_profit_usd = models.DecimalField(max_digits=18, decimal_places=2)
    trader_payout_usd = models.DecimalField(max_digits=18, decimal_places=2)
    payout_percent = models.PositiveSmallIntegerField(default=100)
    verification_ref = models.CharField(max_length=128, unique=True)
    beneficiary_digest = models.CharField(max_length=64)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PENDING_SETTLEMENT,
    )
    settlement_reference = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(realized_profit_usd__gt=0),
                name="mp_sim_payout_profit_positive",
            ),
            models.CheckConstraint(
                condition=Q(trader_payout_usd__gt=0),
                name="mp_sim_payout_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(payout_percent=100),
                name="mp_sim_payout_exactly_full",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="mp_sim_payout_status"),
            models.Index(fields=["account", "-created_at"], name="mp_sim_payout_account"),
        ]

    def clean(self):
        super().clean()
        if self.payout_percent != 100:
            raise ValidationError("Starter30 payout commitment must be exactly 100%")
        if self.realized_profit_usd != self.trader_payout_usd:
            raise ValidationError("Trader payout must equal 100% of realized profit")
        if len(self.beneficiary_digest) != 64:
            raise ValidationError("Beneficiary digest is required")
        if self.status == self.Status.SETTLED and not self.settlement_reference:
            raise ValidationError("Settled payout requires settlement reference")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

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

"""Isolated v1.4.1 DEMO challenge replay journal — NOT an enrollment.

These are operational sequence/audit rows, not a broker account, wallet,
simulator feed attestation, verified trade history, signed customer contract,
or permission to charge a participant. No public API writes to these rows.
The migration MUST NOT run on production before off-host backups, legal
approval, DB capacity and authorized deployment have been confirmed.
"""
from django.db import models
from django.db.models import Q


class PropV141SimState(models.Model):
    challenge_ref = models.CharField(max_length=64, unique=True)
    terms_sha256 = models.CharField(max_length=64)
    trusted_source = models.CharField(max_length=160)
    trusted_key_id = models.CharField(max_length=160)
    last_sequence = models.PositiveBigIntegerField(default=0)
    last_manifest_sha256 = models.CharField(max_length=64, blank=True)
    last_replay_sha256 = models.CharField(max_length=64, blank=True)
    last_as_of = models.DateTimeField(null=True, blank=True)
    last_phase_one_accepted_at = models.DateTimeField(null=True, blank=True)
    last_phase_one_evidence_sha256 = models.CharField(max_length=64, blank=True)
    last_phase_two_started_at = models.DateTimeField(null=True, blank=True)
    last_phase_two_completed_at = models.DateTimeField(null=True, blank=True)
    last_engine_state = models.CharField(max_length=96, default="PENDING_SIGNED_SIMULATOR_FEED")
    last_receipt_sha256 = models.CharField(max_length=64, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["trusted_source", "last_sequence"],
                         name="mp_v141_source_seq"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(last_sequence__gte=0),
                                   name="mp_v141_nonnegative_seq"),
        ]

    def __str__(self):
        return f"MOJ PROP v1.4.1 private DEMO #{self.pk}"


class PropV141SimReceipt(models.Model):
    """Append-only metadata receipt; NOT the original broker/ledger evidence.

    A production-grade external immutable evidence archive must be added
    separately. A hash-only receipt cannot reconstruct original fills.
    """
    state = models.ForeignKey(PropV141SimState, on_delete=models.PROTECT,
                              related_name="replay_receipts")
    sequence = models.PositiveBigIntegerField()
    manifest_id = models.CharField(max_length=160)
    raw_manifest_sha256 = models.CharField(max_length=64)
    replay_sha256 = models.CharField(max_length=64)
    previous_receipt_sha256 = models.CharField(max_length=64)
    receipt_sha256 = models.CharField(max_length=64)
    reported_engine_state = models.CharField(max_length=96)
    as_of = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["state_id", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["state", "sequence"],
                                    name="mp_v141_receipt_state_seq"),
            models.UniqueConstraint(fields=["state", "manifest_id"],
                                    name="mp_v141_receipt_unique_id"),
            models.CheckConstraint(condition=Q(sequence__gte=1),
                                   name="mp_v141_receipt_positive_seq"),
        ]
        indexes = [
            models.Index(fields=["state", "-created_at"],
                         name="mp_v141_recent_receipt"),
        ]

    def __str__(self):
        return f"MOJ PROP v1.4.1 DEMO sequence {self.sequence}"

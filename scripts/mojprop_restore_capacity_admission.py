"""Conservative, source-only capacity admission for an isolated Moj Prop restore.

This check NEVER performs a backup, restore, deployment or storage reservation.
Only fresh, independently measured bytes from the exact destination are valid.
"""
from __future__ import annotations

from dataclasses import dataclass


class CapacityAdmissionDenied(RuntimeError):
    """No verified independent restore capacity."""


@dataclass(frozen=True)
class CapacityEvidence:
    source_database_bytes: int
    source_application_bytes: int
    source_media_bytes: int
    destination_free_bytes: int
    destination_total_bytes: int
    independent_destination: bool
    encrypted_at_rest: bool
    owner_authorized: bool
    measured_at_epoch: int
    now_epoch: int


def require_restore_capacity(evidence: CapacityEvidence) -> int:
    """Return minimum required bytes; fail closed on stale or unsafe evidence.

    Budget is two full source copies plus 25% headroom, rounded up.
    Filesystem free space is not a substitute for tenant quota verification.
    """
    if not isinstance(evidence, CapacityEvidence):
        raise CapacityAdmissionDenied("capacity evidence required")
    values = (
        evidence.source_database_bytes, evidence.source_application_bytes,
        evidence.source_media_bytes, evidence.destination_free_bytes,
        evidence.destination_total_bytes, evidence.measured_at_epoch,
        evidence.now_epoch,
    )
    if any(type(value) is not int or value < 0 for value in values):
        raise CapacityAdmissionDenied("invalid or unknown capacity evidence")
    if any(type(value) is not bool for value in (
        evidence.independent_destination, evidence.encrypted_at_rest,
        evidence.owner_authorized,
    )):
        raise CapacityAdmissionDenied("invalid destination attestations")
    if not all((
        evidence.independent_destination, evidence.encrypted_at_rest,
        evidence.owner_authorized,
    )):
        raise CapacityAdmissionDenied("independent authorized encrypted destination required")
    if not 0 <= evidence.now_epoch - evidence.measured_at_epoch <= 3600:
        raise CapacityAdmissionDenied("destination measurement is stale or future")
    if evidence.destination_free_bytes > evidence.destination_total_bytes:
        raise CapacityAdmissionDenied("free bytes exceed destination size")
    source = sum(values[:3])
    if source <= 0 or evidence.source_database_bytes <= 0:
        raise CapacityAdmissionDenied("complete source inventory required")
    required = (source * 9 + 3) // 4  # 2 copies + 25% source headroom
    if evidence.destination_free_bytes < required:
        raise CapacityAdmissionDenied("insufficient verified independent restore capacity")
    return required

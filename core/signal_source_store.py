"""Atomic staging of authenticated market signals: no sales, payouts or delivery.

This is an internal broker-adapter entrypoint, NOT a customer-facing endpoint.
The unique database key binds an event ID to one brand AND trusted source.
A valid HMAC proves adapter provenance, not trade success or legal permission.
"""
from hashlib import sha256

from django.db import IntegrityError, transaction

from .models import SignalSourceEvent
from .signal_source_evidence import (
    authenticate_signal_source, canonical_signal_bytes,
)


class SignalReceiptRejected(ValueError):
    pass


@transaction.atomic
def stage_signed_signal(*, record, brand, source_id, signature,
                        trusted_source_keys, now, max_age_seconds=86400):
    """Persist an authorized-origin event once; never open paid entitlement.

    The trusted adapter must load keys and trusted UTC time from protected
    server configuration. A second worker cannot claim the same composite ID.
    Publishing/charging needs entirely separate legal, performance, customer
    and settlement approvals.
    """
    result = authenticate_signal_source(
        record=record, brand=brand, source_id=source_id,
        signature=signature, trusted_source_keys=trusted_source_keys,
        seen_event_ids=set(), now=now, max_age_seconds=max_age_seconds,
    )
    if not result.source_authenticated:
        raise SignalReceiptRejected(result.reason)
    canonical = canonical_signal_bytes(
        record=record, brand=brand, source_id=source_id,
    )
    digest = sha256(canonical).hexdigest()
    existing = SignalSourceEvent.objects.select_for_update().filter(
        brand=brand, source_id=source_id, event_id=record["event_id"],
    ).first()
    if existing:
        if (existing.payload_sha256 != digest
                or existing.source_signature != signature
                or existing.canonical_payload != canonical.decode("ascii")):
            raise SignalReceiptRejected("conflicting_signal_event_replay")
        return {
            "result": "already_recorded_pending",
            "event_id": existing.event_id,
            "source_authenticated": True,
            "performance_verified": False,
            "subscription_enabled": False,
            "delivered": False,
        }
    try:
        SignalSourceEvent.objects.create(
            brand=brand, source_id=source_id, event_id=record["event_id"],
            event_at=record["created_at"],
            canonical_payload=canonical.decode("ascii"),
            payload_sha256=digest, source_signature=signature,
        )
    except IntegrityError as exc:
        # Another worker inserted while this transaction was running.
        # The caller must retry read-only reconciliation; never overwrite.
        raise SignalReceiptRejected("concurrent_signal_event_replay") from exc
    return {
        "result": "recorded_pending_audit",
        "event_id": record["event_id"],
        "source_authenticated": True,
        "performance_verified": False,
        "subscription_enabled": False,
        "delivered": False,
    }

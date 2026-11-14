"""Offline authentication of signal *origin*, never of performance or profits.

Only an approved internal broker adapter should know the HMAC secret. A
claimed verified_source=True is NEVER sufficient. The caller must provide a
durable, tenant-scoped event-ID ledger before subscriber distribution.
No public endpoint, email, paid entitlement, or order is created.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import re

from .signal_commercial_catalog import SIGNAL_BRANDS, inspect_signal_record

_SOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z")
_SIGNATURE = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_PRICE = re.compile(r"[0-9]{1,18}(?:\.[0-9]{1,8})?\Z")


@dataclass(frozen=True)
class SignalSourceDecision:
    source_authenticated: bool
    reason: str
    performance_independently_audited: bool = False
    subscription_enabled: bool = False
    signal_delivered: bool = False


def canonical_signal_bytes(*, record, brand, source_id):
    """Bind every proposed signal value to its source AND merchant brand."""
    if brand not in SIGNAL_BRANDS:
        raise ValueError("Unknown market-signal brand")
    if not isinstance(source_id, str) or not _SOURCE_ID.fullmatch(source_id):
        raise ValueError("Invalid trusted provider ID")
    # Restrict untrusted prices BEFORE Decimal parsing in the shared record
    # validator; huge exponents and unbounded strings are not brokerage data.
    if type(record) is not dict or any(
        type(record.get(field)) is not str
        or _SAFE_PRICE.fullmatch(record[field]) is None
        for field in ("entry", "stop_loss", "take_profit")
    ):
        raise ValueError("Unbounded or inexact signal price")
    if not inspect_signal_record(record):
        raise ValueError("Invalid structured signal")
    payload = {
        "version": "MOJ-SIGNAL-SOURCE-v1",
        "brand": brand,
        "source_id": source_id,
        "event_id": record["event_id"],
        "symbol": record["symbol"],
        "side": record["side"],
        "created_at": record["created_at"].isoformat(timespec="microseconds"),
        "entry": record["entry"],
        "stop_loss": record["stop_loss"],
        "take_profit": record["take_profit"],
        "source_claims_verified": record["verified_source"],
    }
    return json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("ascii")


def authenticate_signal_source(*, record, brand, source_id, signature,
                               trusted_source_keys, seen_event_ids,
                               now, max_age_seconds=86400):
    """Authenticate adapter origin and bounded age; never certify outcomes.

    trust_registry keys are (brand, source_id), values are private bytes of
    >=32 bytes; load from protected configuration, NOT customer input.
    seen_event_ids must originate in a durable source/brand-scoped database.
    This read-only validator does not reserve IDs or guarantee atomic replay
    defense. Callers must atomically insert unique IDs after authentication.
    """
    denied = lambda reason: SignalSourceDecision(False, reason)
    try:
        payload = canonical_signal_bytes(
            record=record, brand=brand, source_id=source_id,
        )
    except (TypeError, ValueError, AttributeError, OverflowError):
        return denied("invalid_signal_or_brand")
    if not isinstance(trusted_source_keys, dict):
        return denied("trusted_source_registry_missing")
    secret = trusted_source_keys.get((brand, source_id))
    if not isinstance(secret, bytes) or len(secret) < 32:
        return denied("trusted_source_missing")
    if not isinstance(signature, str) or not _SIGNATURE.fullmatch(signature):
        return denied("malformed_source_signature")
    if not isinstance(now, datetime) or now.tzinfo is None:
        return denied("trusted_clock_missing")
    if now.utcoffset() != timezone.utc.utcoffset(now):
        return denied("trusted_clock_not_utc")
    if not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool) or not 1 <= max_age_seconds <= 604800:
        return denied("invalid_age_limit")
    if seen_event_ids is None or isinstance(seen_event_ids, (str, bytes, dict)):
        return denied("durable_replay_check_missing")
    try:
        age = (now - record["created_at"]).total_seconds()
        if age < -60:
            return denied("signal_from_future")
        if age > max_age_seconds:
            return denied("signal_expired")
        if record["event_id"] in seen_event_ids:
            return denied("signal_event_replayed")
    except (TypeError, ValueError, OverflowError):
        return denied("invalid_replay_or_clock")
    expected = hmac.new(secret, payload, sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return denied("source_signature_mismatch")
    return SignalSourceDecision(True, "trusted_source_signature_valid")

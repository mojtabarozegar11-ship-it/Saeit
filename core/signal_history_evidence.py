"""Authenticated, private signal history QA for the ONE mojtaba.bot.ai worker.

HMAC protects records *after* an approved source adapter received them. A
matching signature is not independent proof of execution, performance,
merchant authority, subscriber entitlement or legal clearance. Never auto-sell.
No network, messaging, trades, payments, DB writes or buyer information.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import re

from .signal_commercial_catalog import SIGNAL_BRANDS, inspect_signal_record

MAX_RECORDS = 10000
MAX_HISTORY_DAYS = 366 * 5
SOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class SignalHistoryRejected(ValueError):
    pass


def _exact(value, field, *, positive=False) -> Decimal:
    if type(value) not in (str, int, Decimal):
        raise SignalHistoryRejected(field + "_precision_or_type")
    try:
        number = Decimal(str(value))
    except (ValueError, InvalidOperation, ArithmeticError):
        raise SignalHistoryRejected(field + "_invalid") from None
    if not number.is_finite() or number < 0 or (positive and number <= 0):
        raise SignalHistoryRejected(field + "_range")
    return number


def _source(source):
    if not isinstance(source, str) or SOURCE_ID.fullmatch(source) is None:
        raise SignalHistoryRejected("source_id_invalid")
    return source


def _canonical(event, source_id, brand):
    """Only fixed non-identifying trade signal fields are signed."""
    _source(source_id)
    if type(brand) is not str or brand not in SIGNAL_BRANDS:
        raise SignalHistoryRejected("brand_not_registered")
    if not inspect_signal_record(event):
        raise SignalHistoryRejected("invalid_signal_record")
    ts = event["created_at"]
    if ts.tzinfo is None or ts.utcoffset() != timedelta(0):
        raise SignalHistoryRejected("timestamp_not_utc")
    return json.dumps({
        "format": "mojtaba.signal.attested_source.v1",
        "source_id": source_id,
        "brand": brand,
        "event_id": event["event_id"],
        "symbol": event["symbol"],
        "side": event["side"],
        "created_at": ts.isoformat(),
        "entry": format(_exact(event["entry"], "entry", positive=True), "f"),
        "stop_loss": format(_exact(event["stop_loss"], "stop", positive=True), "f"),
        "take_profit": format(_exact(event["take_profit"], "target", positive=True), "f"),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def source_digest(event, *, source_id, brand, signing_key):
    """Restricted to a trusted internal adapter, not to HTTP client input."""
    if type(signing_key) is not bytes or len(signing_key) < 32:
        raise SignalHistoryRejected("trusted_adapter_key_missing")
    return hmac.new(signing_key, _canonical(event, source_id, brand), hashlib.sha256).hexdigest()


def verify_source_integrity(event, *, source_id, brand, signing_key, digest):
    if type(digest) is not str or DIGEST.fullmatch(digest) is None:
        return False
    try:
        expected = source_digest(event, source_id=source_id, brand=brand, signing_key=signing_key)
    except (SignalHistoryRejected, TypeError, ValueError, AttributeError):
        return False
    return hmac.compare_digest(expected, digest)


@dataclass(frozen=True)
class SignalAudit:
    event_count: int
    source_id: str
    brand: str
    first_at_utc: str
    last_at_utc: str
    history_digest_sha256: str
    integrity_verified_for_supplied_history: bool
    independent_execution_verified: bool = False
    customer_delivery_verified: bool = False
    realized_performance_verified: bool = False
    subscription_authorized: bool = False
    checkout_enabled: bool = False


def audit_history(entries, *, source_id, brand, signing_key, now_utc):
    """Exact, bounded, monotonic, nonfuture source-authenticated event series.

    Raises on *any* broken row. This is deliberately not a paid-signal adapter.
    """
    _source(source_id)
    if type(brand) is not str or brand not in SIGNAL_BRANDS:
        raise SignalHistoryRejected("brand_not_registered")
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is None:
        raise SignalHistoryRejected("observation_time_invalid")
    if now_utc.utcoffset() != timedelta(0):
        raise SignalHistoryRejected("observation_time_not_utc")
    if not isinstance(entries, (tuple, list)) or not 1 <= len(entries) <= MAX_RECORDS:
        raise SignalHistoryRejected("history_count_invalid")
    if type(signing_key) is not bytes or len(signing_key) < 32:
        raise SignalHistoryRejected("trusted_adapter_key_missing")
    seen = set()
    previous = None
    canonical = []
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"record", "source_digest"}:
            raise SignalHistoryRejected("history_envelope_invalid")
        record = item["record"]
        if not isinstance(record, dict) or not inspect_signal_record(record):
            raise SignalHistoryRejected("signal_record_invalid")
        event_id = record["event_id"]
        if event_id in seen:
            raise SignalHistoryRejected("replayed_event_id")
        seen.add(event_id)
        at = record["created_at"]
        if previous is not None and at <= previous:
            raise SignalHistoryRejected("nonmonotonic_or_duplicate_event_time")
        if at > now_utc:
            raise SignalHistoryRejected("future_dated_signal")
        if now_utc - at > timedelta(days=MAX_HISTORY_DAYS):
            raise SignalHistoryRejected("history_too_old_for_review")
        if not verify_source_integrity(
            record, source_id=source_id, brand=brand, signing_key=signing_key,
            digest=item["source_digest"],
        ):
            raise SignalHistoryRejected("source_signature_mismatch")
        canonical.append(_canonical(record, source_id, brand))
        previous = at
    commitment = hashlib.sha256(b"\n".join(canonical)).hexdigest()
    return SignalAudit(
        event_count=len(entries),
        source_id=source_id,
        brand=brand,
        first_at_utc=entries[0]["record"]["created_at"].isoformat(),
        last_at_utc=entries[-1]["record"]["created_at"].isoformat(),
        history_digest_sha256=commitment,
        integrity_verified_for_supplied_history=True,
    )


def subscription_preflight(*, history: SignalAudit, verified_order_source,
                           timestamped_independent_execution_audit,
                           risk_and_fee_disclosures_approved,
                           jurisdiction_approved, subscriber_delivery_proven,
                           refund_terms_approved, legal_merchant_ready):
    """Explicit gate checklist; does not issue checkout or a subscription."""
    if not isinstance(history, SignalAudit):
        raise SignalHistoryRejected("history_attestation_required")
    checks = {
        "source_history_integrity": history.integrity_verified_for_supplied_history is True,
        "signed_order_source": verified_order_source is True,
        "independent_execution_audit": timestamped_independent_execution_audit is True,
        "risk_and_fee_disclosures": risk_and_fee_disclosures_approved is True,
        "jurisdiction_approved": jurisdiction_approved is True,
        "subscriber_delivery": subscriber_delivery_proven is True,
        "refund_terms": refund_terms_approved is True,
        "merchant_ready": legal_merchant_ready is True,
    }
    return {
        "eligible_for_owner_release_review": all(checks.values()),
        "missing": [key for key, ok in checks.items() if not ok],
        "history_events": history.event_count,
        "account_or_subscriber_created": False,
        "checkout_enabled": False,
        "money_received": None,
        "realized_performance_verified": False,
        "external_contact": False,
    }

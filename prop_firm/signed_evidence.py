"""Signed, internal-only Moj Prop broker/simulator evidence importer.

No public URL; only an explicitly configured trusted upstream adapter may call it.
HMAC authenticates message bytes, not market fairness, broker licenses or custody.
All rows are idempotent and fail closed; no capital or payout side effects.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone as django_timezone

from .models import PropAccount, PropExecution, PropEquityObservation
from .rules import dec


class EvidenceRejected(ValueError):
    pass


def _value(value, field):
    try:
        d = dec(value)
    except (ValueError, TypeError) as exc:
        raise EvidenceRejected(f"{field}: invalid decimal") from exc
    # DecimalField(max_digits=18, decimal_places=4) has 14 integer places.
    # Do not call Decimal.normalize(): extreme but well-formed exponents can
    # raise decimal.Overflow or round a tiny nonzero input to zero under the
    # process decimal context. Both outcomes corrupt the ingestion contract.
    if d.is_zero():
        return Decimal("0")
    if d.adjusted() >= 14:
        raise EvidenceRejected(f"{field}: amount exceeds ledger capacity")
    parts = d.as_tuple()
    effective_exponent = parts.exponent
    if effective_exponent < -4:
        # Ignore only insignificant *stored* trailing zeros, without doing
        # context-dependent arithmetic or rounding away actual evidence.
        for digit in reversed(parts.digits):
            if digit:
                break
            effective_exponent += 1
        if effective_exponent < -4:
            raise EvidenceRejected(f"{field}: precision exceeds ledger")
    return d


def _id(value, field, max_length=160):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", value):
        raise EvidenceRejected(f"{field}: invalid identifier")
    if len(value) > max_length:
        raise EvidenceRejected(f"{field}: too long")
    return value


def _timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EvidenceRejected("Timestamp must be canonical UTC")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceRejected("Timestamp invalid") from exc
    if dt.utcoffset() != timedelta(0):
        raise EvidenceRejected("Timestamp offset invalid")
    return dt


def _signature_ok(*, raw, signature, issued_at, key, account_id, source):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 16_384:
        raise EvidenceRejected("Evidence body must be bounded raw JSON bytes")
    if not isinstance(signature, str) or not re.fullmatch("[a-f0-9]{64}", signature):
        raise EvidenceRejected("Invalid HMAC format")
    if not isinstance(key, str) or len(key) < 32:
        raise EvidenceRejected("Trusted evidence key missing")
    if not isinstance(issued_at, str):
        raise EvidenceRejected("Issued-at header required")
    _timestamp(issued_at)
    msg = b"MOJPROP-EVIDENCE-v1\n" + source.encode() + b"\n" + str(account_id).encode() + b"\n" + issued_at.encode() + b"\n" + raw
    expected = hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise EvidenceRejected("Signed evidence rejected")


def _unique_json_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise EvidenceRejected("Duplicate JSON object key")
        obj[key] = value
    return obj


def _reject_json_constant(value):
    raise EvidenceRejected("Non-finite JSON number")


def ingest_signed_evidence(*, account_id, source, raw, signature, issued_at,
                           now=None):
    """Import one verified immutable identifier into account-owned ledger.

    Security contract:
      - service-to-service only; do not expose as customer-facing Django URL;
      - upstream ID and secret must be configured by verified integration owner;
      - caller's current user never supplies account IDs;
      - signature covers source, account, issued-at and exact raw bytes;
      - transaction-level lock and unique upstream event prevent replay;
      - the source-specific financial claim remains pending operator reconciliation.
    """
    if not isinstance(account_id, UUID):
        raise EvidenceRejected("UUID account ID required")
    source = _id(source, "source", 64)
    keys = getattr(settings, "MOJ_PROP_TRUSTED_EVIDENCE_KEYS", {})
    if not isinstance(keys, dict) or source not in keys:
        raise EvidenceRejected("Source is not allowlisted")
    _signature_ok(raw=raw, signature=signature, issued_at=issued_at,
                  key=keys[source], account_id=account_id, source=source)
    timestamp = _timestamp(issued_at)
    moment = django_timezone.now() if now is None else now
    if moment.tzinfo is None:
        raise EvidenceRejected("Server clock must be timezone-aware")
    if abs((moment - timestamp).total_seconds()) > 300:
        raise EvidenceRejected("Expired or future evidence")
    try:
        envelope = json.loads(raw.decode("utf-8"),
                              object_pairs_hook=_unique_json_pairs,
                              parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        # A signed but excessively nested packet must fail closed, not raise HTTP 500.
        raise EvidenceRejected("Invalid UTF-8 JSON evidence") from exc
    # Bound structural complexity independently of the JSON parser recursion limit.
    stack = [(envelope, 0)]
    while stack:
        node, depth = stack.pop()
        if isinstance(node, (dict, list)):
            if depth > 64:
                raise EvidenceRejected("JSON nesting limit exceeded")
            children = node.values() if isinstance(node, dict) else node
            stack.extend((child, depth + 1) for child in children)
    if not isinstance(envelope, dict) or set(envelope) != {
        "account_id", "event_id", "event_type", "recorded_at", "data"
    }:
        raise EvidenceRejected("Unexpected evidence envelope")
    if envelope["account_id"] != str(account_id):
        raise EvidenceRejected("Account identity differs from signed envelope")
    event_id = _id(envelope["event_id"], "event_id")
    event_type = envelope["event_type"]
    if event_type not in ("execution", "equity"):
        raise EvidenceRejected("Unsupported evidence event")
    occurred = _timestamp(envelope["recorded_at"])
    if occurred > moment + timedelta(seconds=30):
        raise EvidenceRejected("Event timestamp in future")
    data = envelope["data"]
    if not isinstance(data, dict):
        raise EvidenceRejected("Event data must be an object")

    digest = hashlib.sha256(raw).hexdigest()
    with transaction.atomic():
        account = PropAccount.objects.select_for_update().filter(pk=account_id).first()
        if account is None or account.status in (
            PropAccount.Status.BREACHED, PropAccount.Status.CLOSED):
            raise EvidenceRejected("Account not eligible for ingestion")
        if event_type == "execution":
            base = {"symbol", "gross_usd", "fees_usd"}
            enriched = base | {"position_id", "execution_origin"}
            if set(data) not in (base, enriched):
                raise EvidenceRejected("Execution schema mismatch")
            # Legacy signed events remain usable for P&L, but do NOT qualify
            # as uniquely closed trades unless a signed position ID exists.
            if set(data) == enriched:
                position_id = _id(data["position_id"], "position_id")
                if data["execution_origin"] not in ("manual", "bot", "unknown"):
                    raise EvidenceRejected("Execution origin must be manual, bot or unknown")
                origin = data["execution_origin"]
            else:
                position_id = ""
                origin = "unknown"
            symbol = _id(data["symbol"], "symbol", 32)
            gross = _value(data["gross_usd"], "gross_usd")
            fees = _value(data["fees_usd"], "fees_usd")
            if fees < 0:
                raise EvidenceRejected("Negative fees")
            target = PropExecution
            incoming = dict(
                account=account, external_event_id=event_id,
                data_source=source, symbol=symbol, closed_at=occurred,
                external_position_id=position_id, execution_origin=origin,
                gross_realized_usd=gross, total_fees_usd=fees,
                reconciliation_status="pending", evidence_digest=digest,
            )
        else:
            if set(data) != {"equity_usd", "is_session_open"}:
                raise EvidenceRejected("Equity schema mismatch")
            equity = _value(data["equity_usd"], "equity_usd")
            if equity < 0 or type(data["is_session_open"]) is not bool:
                raise EvidenceRejected("Invalid equity mark")
            target = PropEquityObservation
            incoming = dict(
                account=account, external_event_id=event_id,
                data_source=source,
                observed_at=occurred, equity_usd=equity,
                is_session_open=data["is_session_open"],
                reconciliation_status="pending", evidence_digest=digest,
            )

        # Upstream IDs must be unique across both evidence event types.
        other = (PropEquityObservation if event_type == "execution"
                 else PropExecution)
        if other.objects.filter(account=account, external_event_id=event_id).exists():
            raise EvidenceRejected("Upstream event ID reused across event types")

        existing = target.objects.filter(account=account, external_event_id=event_id).first()
        if existing:
            if existing.evidence_digest != digest:
                raise EvidenceRejected("Upstream replay ID has conflicting evidence")
            return {"event_id": event_id, "result": "already_recorded",
                    "verified": False, "digest": digest}

        # A forged customer post or duplicated upstream ID cannot create a payout:
        # ingestion leaves every record pending until independent verification.
        item = target(**incoming)
        item.full_clean()
        try:
            item.save(force_insert=True)
        except IntegrityError as exc:
            raise EvidenceRejected("Duplicate event race; reconcile manually") from exc
        return {"event_id": event_id, "result": "recorded_pending",
                "verified": False, "digest": digest}

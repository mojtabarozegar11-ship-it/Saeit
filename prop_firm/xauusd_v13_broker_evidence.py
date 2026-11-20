"""Version-bound, non-executing XAUUSD broker evidence bridge (draft v1.3).

A valid HMAC proves a configured upstream signed specific bytes; it DOES NOT
prove the signer is the broker, that any capital exists, or that trading is
lawfully authorized. No web requests, database writes, orders or payments.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from .independent_attestation import (
    AttestationRejected, KIND_BROKER, verify_attestation,
)
from .xauusd_v13_preflight import (
    DRAFT_CONTRACT_VERSION, GoldOrderSnapshot, GoldReview, exact,
    review_gold_order,
)

SCHEMA = "mojprop.xauusd.v13.broker-risk.v1"
SUBJECT = "moj-prop:MOJ-PROP-01:broker"
MAX_BYTES = 16384
MAX_POSITIONS = 64
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z")
_BOUND_FIELDS = (
    "product", "contract_version", "symbol", "account_currency",
    "initial_capital", "equity", "day_open_equity",
    "side", "mid_price_per_oz", "stop_price_per_oz",
    "lot_quantity", "minimum_lot", "lot_step", "ounces_per_lot",
    "min_stop_distance_per_oz", "full_spread_per_oz",
    "slippage_reserve_per_oz", "roundtrip_fees_usd",
    "margin_required_usd", "free_margin_usd",
)
_REQUIRED = frozenset((
    "schema", "account_ref", "source", "quote_ref", "quote_at",
    "reported_open_position_count", "reported_open_risk_usd",
    "open_positions",
) + _BOUND_FIELDS)
_POSITION_FIELDS = frozenset(("position_ref", "symbol", "risk_to_stop_usd"))


class GoldEvidenceRejected(ValueError):
    """Evidence invalid or unavailable; never an authorization to trade."""


@dataclass(frozen=True)
class BrokerEvidenceReview:
    snapshot_sha256: str
    attestation_id: str
    authenticated_upstream_source: str
    positions_reconciled_in_signed_packet: int
    result: GoldReview
    risk_review_only: bool = True
    broker_counterparty_independently_verified_by_this_module: bool = False
    fund_capital_verified_by_this_module: bool = False
    customer_contract_authorized: bool = False
    customer_invoice_authorized: bool = False
    live_order_authorized: bool = False
    payout_authorized: bool = False


def _reject_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GoldEvidenceRejected("duplicate JSON object field")
        result[key] = value
    return result


def _reject_non_finite(value):
    raise GoldEvidenceRejected("non-finite number in broker packet")


def _ref(value, field):
    if type(value) is not str or _REF.fullmatch(value) is None:
        raise GoldEvidenceRejected(field + " must be an opaque reference")
    return value


def _utc_time(value):
    if type(value) is not str or not value.endswith("Z"):
        raise GoldEvidenceRejected("canonical UTC quote timestamp required")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise GoldEvidenceRejected("invalid quote timestamp") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise GoldEvidenceRejected("quote must be UTC") 
    return parsed


def review_attested_xauusd_snapshot(
    *, raw_broker_snapshot: bytes, attestation_packet: dict,
    trusted_attestation_keys: dict, expected_source: str,
    expected_account_ref: str, now: datetime,
) -> BrokerEvidenceReview:
    """Check HMAC/digest/account/position reconciliation before risk math.

    trusted_attestation_keys and expected_* must come from restricted server
    configuration, not a buyer or trading strategy. The signer is not proven
    to be a regulated broker by the HMAC alone. Replay prevention, broker
    identity and external funding are OUTSIDE this pure read-only function.
    """
    _ref(expected_source, "trusted source")
    _ref(expected_account_ref, "account")
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
        raise GoldEvidenceRejected("trusted timezone-aware assessment time required")
    if (type(raw_broker_snapshot) is not bytes
            or not 0 < len(raw_broker_snapshot) <= MAX_BYTES):
        raise GoldEvidenceRejected("bounded raw broker snapshot required")
    try:
        doc = json.loads(
            raw_broker_snapshot.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_non_finite,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise GoldEvidenceRejected("invalid signed broker JSON") from exc
    if type(doc) is not dict or frozenset(doc) != _REQUIRED:
        raise GoldEvidenceRejected("broker snapshot schema mismatch")
    if doc["schema"] != SCHEMA:
        raise GoldEvidenceRejected("unsupported broker snapshot schema")
    if (doc["account_ref"] != expected_account_ref
            or doc["source"] != expected_source):
        raise GoldEvidenceRejected("broker account or source mismatch")
    _ref(doc["account_ref"], "account")
    _ref(doc["source"], "source")
    _ref(doc["quote_ref"], "quote")
    if doc["product"] != "MOJ-PROP-01" or doc["contract_version"] != DRAFT_CONTRACT_VERSION:
        raise GoldEvidenceRejected("contract and SKU must be v1.3 gold draft")
    if doc["symbol"] != "XAUUSD" or doc["account_currency"] != "USD":
        raise GoldEvidenceRejected("signed packet is not USD-denominated XAUUSD")

    positions = doc["open_positions"]
    count = doc["reported_open_position_count"]
    if (type(positions) is not list or len(positions) > MAX_POSITIONS
            or type(count) is not int or count != len(positions)):
        raise GoldEvidenceRejected("open position count mismatch")
    opened = Decimal("0")
    seen = set()
    for position in positions:
        if type(position) is not dict or frozenset(position) != _POSITION_FIELDS:
            raise GoldEvidenceRejected("open position schema mismatch")
        ref = _ref(position["position_ref"], "position")
        if ref in seen:
            raise GoldEvidenceRejected("duplicate open position reference")
        seen.add(ref)
        if position["symbol"] != "XAUUSD":
            raise GoldEvidenceRejected("unreconciled non-gold open position")
        try:
            opened += exact(position["risk_to_stop_usd"], allow_zero=True)
        except ValueError as exc:
            raise GoldEvidenceRejected("invalid signed position risk") from exc
    try:
        if opened != exact(doc["reported_open_risk_usd"], allow_zero=True):
            raise GoldEvidenceRejected("reported open-risk sum differs")
    except ValueError as exc:
        raise GoldEvidenceRejected("invalid reported open risk") from exc
    try:
        attested = verify_attestation(
            attestation_packet, trusted_attestation_keys, now=now,
        )
    except AttestationRejected as exc:
        raise GoldEvidenceRejected("external attestation rejected") from exc
    if (attested.kind != KIND_BROKER or attested.subject_id != SUBJECT
            or attested.source != expected_source):
        raise GoldEvidenceRejected("attestation not bound to expected broker context")
    digest = hashlib.sha256(raw_broker_snapshot).hexdigest()
    if not hmac.compare_digest(digest, attested.evidence_digest):
        raise GoldEvidenceRejected("signed digest differs from exact broker snapshot")
    quote = _utc_time(doc["quote_at"])
    kwargs = {field: doc[field] for field in _BOUND_FIELDS}
    try:
        snapshot = GoldOrderSnapshot(
            **kwargs,
            existing_open_remaining_stop_risk=str(opened),
            quote_at=quote,
            assessed_at=now,
            broker_snapshot_claimed=True,
            complete_open_positions_claimed=True,
            symbol_spec_claimed=True,
            stop_claimed=True,
        )
        result = review_gold_order(snapshot)
    except (ValueError, RuntimeError, TypeError) as exc:
        raise GoldEvidenceRejected("risk snapshot failed canonical review") from exc
    return BrokerEvidenceReview(
        snapshot_sha256=digest,
        attestation_id=attested.attestation_id,
        authenticated_upstream_source=attested.source,
        positions_reconciled_in_signed_packet=count,
        result=result,
    )

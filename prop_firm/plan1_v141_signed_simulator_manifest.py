"""HMAC-bound intake for a proposed independent MOJ PROP v1.4.1 DEMO ledger.

This checks integrity of one bounded machine-generated snapshot from a
configured simulator adapter. It does NOT prove the signer is a regulated
broker, that an underlying event was genuine, that the ledger is complete,
or that customer payments, real brokerage accounts or capital are authorized.
The caller must supply an allowlisted signer/key, trusted challenge identity,
current time and an ATOMIC monotone per-challenge sequence from safe storage.
No HTTP, filesystem, database write, payment, trading or secret logging.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import re

from .plan1_v141_simulated_challenge_engine import (
    EngineSnapshot, SimulatedClosedFill, SimulatedEquityMark,
    ChallengeReplayDecision, replay_simulated_challenge,
)
from .plan1_v14_social_or_50_terms import review_prospective_terms

SCHEMA = "mojprop.v141.simulated-ledger-hmac.v1"
SIGN_PREFIX = b"MOJPROP-V141-SIMULATED-LEDGER-v1\n"
MAX_MANIFEST_BYTES = 3_000_000
MAX_MANIFEST_AGE = timedelta(minutes=10)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MANIFEST = frozenset(("schema","source","key_id","manifest_id","sequence","issued_at","snapshot"))
_SNAPSHOT = frozenset(("challenge_ref","accepted_terms_sha256",
    "evaluation_started_at","phase_one_accepted_at","phase_two_started_at",
    "phase_two_completed_at","as_of","closed_fills","equity_marks"))
_FILL = frozenset(("phase","data_source","external_event_id",
    "external_position_id","symbol","closed_at","gross_realized_usd",
    "total_fees_usd","position_fully_closed","reconciliation_status","evidence_sha256"))
_MARK = frozenset(("phase","data_source","external_event_id","observed_at",
    "equity_usd","is_utc_day_open","reconciliation_status","evidence_sha256"))


class LedgerManifestRejected(ValueError):
    """The caller-supplied manifest does not meet the signed intake contract."""


@dataclass(frozen=True)
class HmacLedgerReview:
    signer_id: str
    source: str
    manifest_id: str
    sequence: int
    raw_manifest_sha256: str
    calculation: ChallengeReplayDecision
    configured_adapter_hmac_authenticated: bool = True
    trusted_persistent_replay_registry_implemented_here: bool = False
    regulated_broker_identity_proven: bool = False
    independent_event_history_completeness_proven: bool = False
    merchant_legal_approval_proven: bool = False
    customer_contract_signed: bool = False
    checkout_authorized: bool = False
    paid_enrollment_authorized: bool = False
    real_orders_authorized: bool = False
    payout_authorized: bool = False


def _no_dupes(pairs):
    doc = {}
    for key,value in pairs:
        if key in doc:
            raise LedgerManifestRejected("duplicate JSON key rejected")
        doc[key] = value
    return doc


def _no_nonfinite(value):
    raise LedgerManifestRejected("nonfinite JSON number rejected")


def _no_float(value):
    raise LedgerManifestRejected("monetary values must be exact strings")


def _timestamp(value, name):
    if type(value) is not str or not value.endswith("Z"):
        raise LedgerManifestRejected(f"{name}: canonical UTC Z timestamp required")
    try:
        parsed = datetime.fromisoformat(value[:-1]+"+00:00")
    except ValueError as exc:
        raise LedgerManifestRejected(f"{name}: invalid timestamp") from exc
    if parsed.utcoffset() != timedelta(0) or parsed.isoformat().replace("+00:00","Z") != value:
        raise LedgerManifestRejected(f"{name}: noncanonical UTC timestamp")
    return parsed


def _shape(obj, expected, name):
    if type(obj) is not dict or frozenset(obj) != expected:
        raise LedgerManifestRejected(name + " schema mismatch")


def _id(value,name):
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise LedgerManifestRejected(name + ": invalid identifier")
    return value


def _rows(raw, schema, cls, time_key):
    if type(raw) is not list or len(raw) > 5000:
        raise LedgerManifestRejected("bounded event list required")
    rows = []
    for entry in raw:
        _shape(entry,schema,"signed event")
        data=dict(entry)
        data[time_key]=_timestamp(data[time_key],time_key)
        rows.append(cls(**data))
    return tuple(rows)


def verify_and_replay_signed_simulator_manifest(
    *, raw_manifest: bytes, hmac_signature: str,
    trusted_signer_keys: dict, expected_source: str, expected_key_id: str,
    expected_manifest_id: str, expected_challenge_ref: str,
    expected_sequence: int, now: datetime,
) -> HmacLedgerReview:
    """Verify exact signed bytes AND expected replay sequence before replay.

    An HMAC key only authenticates a configured sender. External authorized
    services must independently verify trade/equity evidence, persist sequence
    increments atomically, and ensure source history is complete.
    """
    if (type(raw_manifest) is not bytes or not 0 < len(raw_manifest) <= MAX_MANIFEST_BYTES
            or type(hmac_signature) is not str or _HEX.fullmatch(hmac_signature) is None):
        raise LedgerManifestRejected("bounded bytes and signature required")
    if type(trusted_signer_keys) is not dict:
        raise LedgerManifestRejected("trusted signer registry required")
    for value,name in ((expected_source,"source"),(expected_key_id,"key_id"),
                       (expected_manifest_id,"manifest_id"),
                       (expected_challenge_ref,"challenge_ref")):
        _id(value,name)
    if type(expected_sequence) is not int or expected_sequence < 1:
        raise LedgerManifestRejected("trusted monotone sequence required")
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
        raise LedgerManifestRejected("trusted timezone-aware clock required")
    secret=trusted_signer_keys.get(expected_key_id)
    if type(secret) is not bytes or len(secret) < 32:
        raise LedgerManifestRejected("configured server-owned HMAC key required")
    correct=hmac.new(secret,SIGN_PREFIX+raw_manifest,"sha256").hexdigest()
    if not hmac.compare_digest(correct,hmac_signature):
        raise LedgerManifestRejected("signed simulator manifest authentication failed")
    try:
        doc=json.loads(raw_manifest.decode("utf-8"),object_pairs_hook=_no_dupes,
                       parse_float=_no_float,parse_constant=_no_nonfinite)
    except (ValueError,UnicodeError,RecursionError) as exc:
        raise LedgerManifestRejected("invalid signed JSON") from exc
    _shape(doc,_MANIFEST,"simulator manifest")
    if doc["schema"] != SCHEMA:
        raise LedgerManifestRejected("wrong manifest schema")
    if (doc["source"] != expected_source or doc["key_id"] != expected_key_id
            or doc["manifest_id"] != expected_manifest_id
            or type(doc["sequence"]) is not int
            or doc["sequence"] != expected_sequence):
        raise LedgerManifestRejected("source, key, manifest ID or sequence mismatch")
    _shape(doc["snapshot"],_SNAPSHOT,"challenge snapshot")
    t=review_prospective_terms()
    data=dict(doc["snapshot"])
    if (data["challenge_ref"] != expected_challenge_ref
            or data["accepted_terms_sha256"] != t.contract_candidate_sha256):
        raise LedgerManifestRejected("wrong challenge or contract fingerprint")
    issued=_timestamp(doc["issued_at"],"issued_at")
    now=now.astimezone(timezone.utc)
    if not timedelta(0) <= now-issued <= MAX_MANIFEST_AGE:
        raise LedgerManifestRejected("stale or future signed manifest")
    for key in ("evaluation_started_at","as_of"):
        data[key]=_timestamp(data[key],key)
    for key in ("phase_one_accepted_at","phase_two_started_at","phase_two_completed_at"):
        if data[key] is not None:
            data[key]=_timestamp(data[key],key)
    data["closed_fills"]=_rows(data["closed_fills"],_FILL,SimulatedClosedFill,"closed_at")
    data["equity_marks"]=_rows(data["equity_marks"],_MARK,SimulatedEquityMark,"observed_at")
    if len(data["closed_fills"])+len(data["equity_marks"]) > 5000:
        raise LedgerManifestRejected("combined ledger exceeds bounded replay")
    if data["as_of"] > issued:
        raise LedgerManifestRejected("assessment cannot predate signed manifest data")
    try:
        result=replay_simulated_challenge(snapshot=EngineSnapshot(**data))
    except (ValueError,TypeError,ArithmeticError) as exc:
        raise LedgerManifestRejected("signed simulator data rejected by engine") from exc
    return HmacLedgerReview(
        signer_id=expected_key_id,source=expected_source,
        manifest_id=expected_manifest_id,sequence=expected_sequence,
        raw_manifest_sha256=sha256(raw_manifest).hexdigest(),
        calculation=result,
    )

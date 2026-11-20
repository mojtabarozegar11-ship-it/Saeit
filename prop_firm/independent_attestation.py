"""Independent, signed readiness attestations for Moj Prop.

This module verifies a bounded capital/broker attestation envelope from an
allowlisted independent integration. It never creates an invoice, activates
checkout, moves funds, places an order or marks a customer account funded.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

KIND_CAPITAL = "capital"
KIND_BROKER = "broker"
ATTESTATION_KINDS = frozenset((KIND_CAPITAL, KIND_BROKER))
MAX_ATTESTATION_LIFETIME = timedelta(days=30)
_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}")
_HEX_DIGEST_PATTERN = re.compile(r"[a-f0-9]{64}")
_REQUIRED_FIELDS = frozenset({
    "attestation_id", "kind", "subject_id", "source", "key_id",
    "issued_at", "expires_at", "evidence_digest", "signature",
})


class AttestationRejected(ValueError):
    """Raised when a readiness attestation cannot be trusted."""


@dataclass(frozen=True)
class IndependentAttestation:
    attestation_id: str
    kind: str
    subject_id: str
    source: str
    key_id: str
    issued_at: datetime
    expires_at: datetime
    evidence_digest: str


@dataclass(frozen=True)
class AttestationAssessment:
    capital: IndependentAttestation | None
    broker: IndependentAttestation | None
    errors: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return self.capital is not None and self.broker is not None

    @property
    def missing(self) -> tuple[str, ...]:
        missing = []
        if self.capital is None:
            missing.append(KIND_CAPITAL)
        if self.broker is None:
            missing.append(KIND_BROKER)
        return tuple(missing)


def _identifier(value, field):
    if type(value) is not str or not _ID_PATTERN.fullmatch(value):
        raise AttestationRejected(f"{field}: invalid identifier")
    return value


def _utc_timestamp(value, field):
    if type(value) is not str or not value.endswith("Z"):
        raise AttestationRejected(f"{field}: canonical UTC timestamp required")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AttestationRejected(f"{field}: invalid timestamp") from exc
    if parsed.utcoffset() != timedelta(0):
        raise AttestationRejected(f"{field}: UTC offset required")
    return parsed


def _canonical_body(packet):
    body = {key: packet[key] for key in sorted(packet) if key != "signature"}
    try:
        return json.dumps(
            body, ensure_ascii=True, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AttestationRejected("Attestation body is not canonical JSON") from exc


def verify_attestation(packet, trusted_keys, *, now=None):
    """Verify one independent capital or broker attestation.

    The caller must supply a protected key registry. The owner/self key names
    are rejected so an owner declaration cannot masquerade as independence.
    """
    if type(packet) is not dict or frozenset(packet) != _REQUIRED_FIELDS:
        raise AttestationRejected("Attestation schema mismatch")
    if type(trusted_keys) is not dict:
        raise AttestationRejected("Trusted attestation registry required")

    attestation_id = _identifier(packet["attestation_id"], "attestation_id")
    kind = packet["kind"]
    if type(kind) is not str or kind not in ATTESTATION_KINDS:
        raise AttestationRejected("Unsupported attestation kind")
    subject_id = _identifier(packet["subject_id"], "subject_id")
    source = _identifier(packet["source"], "source")
    key_id = _identifier(packet["key_id"], "key_id")
    if key_id.lower() in {"owner", "self", "mojtaba", "owner_declared"}:
        raise AttestationRejected("Owner declaration cannot be independent")
    key = trusted_keys.get(key_id)
    if type(key) is not str or len(key) < 32:
        raise AttestationRejected("Trusted attestation key missing")
    signature = packet["signature"]
    if type(signature) is not str or not re.fullmatch(r"[a-f0-9]{64}", signature):
        raise AttestationRejected("Invalid attestation signature")
    issued_at = _utc_timestamp(packet["issued_at"], "issued_at")
    expires_at = _utc_timestamp(packet["expires_at"], "expires_at")
    if expires_at <= issued_at:
        raise AttestationRejected("Attestation expiry must follow issuance")
    if expires_at - issued_at > MAX_ATTESTATION_LIFETIME:
        raise AttestationRejected("Attestation lifetime exceeds 30 days")
    digest = packet["evidence_digest"]
    if (type(digest) is not str or not _HEX_DIGEST_PATTERN.fullmatch(digest)
            or digest == "0" * 64):
        raise AttestationRejected("Evidence digest must be lowercase SHA-256")
    moment = datetime.now(timezone.utc) if now is None else now
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise AttestationRejected("Attestation clock must be timezone-aware")
    moment = moment.astimezone(timezone.utc)
    if moment < issued_at or moment > expires_at:
        raise AttestationRejected("Attestation is expired or not yet valid")

    expected = hmac.new(
        key.encode("utf-8"),
        b"MOJPROP-ATTESTATION-v1\n" + _canonical_body(packet),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AttestationRejected("Attestation signature rejected")

    return IndependentAttestation(
        attestation_id=attestation_id,
        kind=kind,
        subject_id=subject_id,
        source=source,
        key_id=key_id,
        issued_at=issued_at,
        expires_at=expires_at,
        evidence_digest=digest,
    )


def assess_independent_attestations(packets=None, trusted_keys=None, *,
                                    now=None, plan_code=None):
    """Collect at most one valid attestation per kind; fail closed on errors."""
    if packets is None:
        return AttestationAssessment(capital=None, broker=None, errors=())
    if type(packets) not in (list, tuple):
        return AttestationAssessment(
            capital=None, broker=None, errors=("packet_list_required",)
        )
    if len(packets) > 8:
        return AttestationAssessment(
            capital=None, broker=None, errors=("too_many_attestations",)
        )
    if plan_code is not None:
        _identifier(plan_code, "plan_code")
    capital = None
    broker = None
    errors = []
    seen_ids = set()
    for packet in packets:
        try:
            verified = verify_attestation(packet, trusted_keys, now=now)
        except AttestationRejected as exc:
            errors.append(str(exc))
            continue
        if verified.attestation_id in seen_ids:
            errors.append("duplicate_attestation_id")
            continue
        seen_ids.add(verified.attestation_id)
        if (plan_code is not None
                and verified.subject_id != f"moj-prop:{plan_code}:{verified.kind}"):
            errors.append("attestation_plan_subject_mismatch")
            continue
        if verified.kind == KIND_CAPITAL:
            if capital is not None:
                errors.append("duplicate_capital_attestation")
            else:
                capital = verified
        elif broker is not None:
            errors.append("duplicate_broker_attestation")
        else:
            broker = verified
    if capital is not None and broker is not None:
        if capital.key_id == broker.key_id:
            errors.append("capital_broker_must_have_distinct_keys")
        if capital.source == broker.source:
            errors.append("capital_broker_must_have_distinct_sources")
        if capital.evidence_digest == broker.evidence_digest:
            errors.append("capital_broker_must_have_distinct_evidence")
        if (type(trusted_keys) is dict
                and trusted_keys.get(capital.key_id) == trusted_keys.get(broker.key_id)):
            errors.append("capital_broker_share_key_material")
    if errors:
        # Invalid or conflicting upstream evidence must not remain available
        # as a partially valid certificate for downstream release gates.
        return AttestationAssessment(capital=None, broker=None, errors=tuple(errors))
    return AttestationAssessment(
        capital=capital, broker=broker, errors=()
    )

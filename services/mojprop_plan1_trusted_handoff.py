"""Server-only B -> C handoff for REAL MOJ-PROP-01; never a payment action.

This is a cryptographically authenticated *prepayment review*, NOT the canonical
PropChallengeEnrollment: in PR #2310 that model describes a CONFIRMED purchase.
A production B service must issue a signed review envelope AFTER it validates
its intake/reviewer records and independently verifies actual source documents.
Twenty named trusted services must separately sign their own fact payloads.
The key registry and customer identity MUST be resolved by server code, not HTTP.
Passing these offline checks does not prove an actual legal/funding/broker status.
No address, RPC, checkout, payment intent, ledger credit or activation is emitted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from collections.abc import Mapping
import hmac
import json
import re

from services.mojprop_real_plan1_invoice_boundary import (
    Enrollment, TrustedFact, REQUIRED_PROOFS, authorize_candidate,
    InvoiceBoundaryRejected, ORDER, PRODUCT, VERSION, NETWORK, AMOUNT_SUN, HEX64,
)

_REVIEW_REF = re.compile(r"PROP1-REVIEW-[A-F0-9]{32}\Z")
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,95}\Z")
_HEX64 = HEX64
_B_REVIEW_SCOPE = "mojprop.plan1.b.signed-preorder-review.v1"
_C_FACT_SCOPE = "mojprop.plan1.c.trusted-fact.v1"
_MAX_LIFETIME_SEC = 86_400


class HandoffRejected(ValueError):
    """No permission for payable invoice, settlement or confirmed enrollment."""


@dataclass(frozen=True)
class ReviewSnapshot:
    order_ref: str
    review_ref: str
    original_request_ref: str
    buyer_id: str
    seller_id: str
    sku: str
    terms_version: str
    chain: str
    token_symbol: str
    amount_sun: int
    signed_terms_sha256: str
    contract_pdf_sha256: str
    refund_disclosure_sha256: str
    buyer_signature_proof_sha256: str
    seller_signature_proof_sha256: str
    reviewer_packet_sha256: str
    issued_at_sec: int
    expires_at_sec: int
    state: str
    payable: bool
    invoice_created: bool
    settlement_verified: bool
    enrollment_created: bool
    signature_hex: str


@dataclass(frozen=True)
class TrustedAuthority:
    issuer: str
    key_id: str
    secret: bytes


@dataclass(frozen=True)
class SignedFact:
    name: str
    issuer: str
    key_id: str
    subject: str
    buyer_id: str
    passed: bool
    evidence_sha256: str
    checked_at: int
    valid_until: int
    signature_hex: str


def _valid_digest(v: object) -> bool:
    return type(v) is str and _HEX64.fullmatch(v) is not None and v != "0" * 64


def _signed_bytes(scope: str, record: ReviewSnapshot | SignedFact) -> bytes:
    """Canonical versioned signing contract for private B/C producer services."""
    fields = asdict(record)
    fields.pop("signature_hex")
    return json.dumps(
        {"scope": scope, "fields": fields}, sort_keys=True,
        separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode("ascii")


def _verify_signature(record: ReviewSnapshot | SignedFact, scope: str, secret: bytes) -> None:
    if (type(secret) is not bytes or len(secret) < 32
            or type(record.signature_hex) is not str
            or _HEX64.fullmatch(record.signature_hex) is None):
        raise HandoffRejected("signed trusted service evidence required")
    digest = hmac.new(secret, _signed_bytes(scope, record), sha256).hexdigest()
    if not hmac.compare_digest(record.signature_hex, digest):
        raise HandoffRejected("invalid source signature or modified signed payload")


def validate_signed_b_review(
    review: ReviewSnapshot, *, order_ref: str, buyer_id: str,
    seller_id: str, reviewer_key: bytes, now: int,
    expected_signed_terms_sha256: str,
) -> str:
    """Authenticates a private, nonpayable B projection; cannot sign for B."""
    if type(review) is not ReviewSnapshot or type(now) is not int or now <= 0:
        raise HandoffRejected("typed private review and server time required")
    if (type(order_ref) is not str or ORDER.fullmatch(order_ref) is None
            or any(type(v) is not str or _REF.fullmatch(v) is None
                   for v in (buyer_id, seller_id))):
        raise HandoffRejected("server authenticated order/buyer/seller required")
    if (type(review.order_ref) is not str or review.order_ref != order_ref
            or type(review.review_ref) is not str
            or _REVIEW_REF.fullmatch(review.review_ref) is None
            or type(review.original_request_ref) is not str
            or _REF.fullmatch(review.original_request_ref) is None
            or review.buyer_id != buyer_id or review.seller_id != seller_id):
        raise HandoffRejected("B review is not bound to this buyer, seller and order")
    if (review.sku != PRODUCT or review.terms_version != VERSION
            or review.chain != "TRON-mainnet" or review.token_symbol != "TRX"
            or type(review.amount_sun) is not int or review.amount_sun != AMOUNT_SUN):
        raise HandoffRejected("not the genuine v1.2 native-TRX Plan 1 contract")
    for key in ("signed_terms_sha256", "contract_pdf_sha256",
                "refund_disclosure_sha256", "buyer_signature_proof_sha256",
                "seller_signature_proof_sha256", "reviewer_packet_sha256"):
        if not _valid_digest(getattr(review, key)):
            raise HandoffRejected("missing signed legal or refund evidence: " + key)
    if (not _valid_digest(expected_signed_terms_sha256)
            or review.signed_terms_sha256 != expected_signed_terms_sha256):
        raise HandoffRejected("independent bilingual signed terms digest mismatch")
    if (type(review.issued_at_sec) is not int or type(review.expires_at_sec) is not int
            or not review.issued_at_sec <= now < review.expires_at_sec
            or not 0 < review.expires_at_sec - review.issued_at_sec <= _MAX_LIFETIME_SEC):
        raise HandoffRejected("review expired, future dated or too long-lived")
    if (review.state != "PRIVATE_NONPAYABLE_CONTRACT_REVIEW"
            or review.payable is not False
            or review.invoice_created is not False
            or review.settlement_verified is not False
            or review.enrollment_created is not False):
        raise HandoffRejected("confirmed enrollment or payment state cannot be inferred")
    _verify_signature(review, _B_REVIEW_SCOPE, reviewer_key)
    return sha256(_signed_bytes(_B_REVIEW_SCOPE, review)).hexdigest()


def review_authenticated_preorder(
    *, review: ReviewSnapshot, order_ref: str, buyer_id: str, seller_id: str,
    reviewer_key: bytes, signed_facts: Mapping[str, SignedFact],
    authorities: Mapping[str, TrustedAuthority],
    independent_terms_sha256: str, now: int,
) -> dict:
    """Derives a NONPAYABLE C audit handoff using B signature + 20 scoped MACs.

    The enrolled purchase record may be created ONLY by the future independent
    real-payment settlement adapter AFTER proven chain finality and atomic global
    UNIQUE(network,txid). This function must never create that record.
    """
    review_hash = validate_signed_b_review(
        review, order_ref=order_ref, buyer_id=buyer_id,
        seller_id=seller_id, reviewer_key=reviewer_key, now=now,
        expected_signed_terms_sha256=independent_terms_sha256,
    )
    if (type(signed_facts) is not dict or type(authorities) is not dict
            or set(signed_facts) != set(REQUIRED_PROOFS)
            or set(authorities) != set(REQUIRED_PROOFS)):
        raise HandoffRejected("exact independently scoped 20 fact attestations required")
    keys: set[bytes] = set()
    tags: set[tuple[str, str]] = set()
    facts: dict[str, TrustedFact] = {}
    trusted_sources: dict[str, str] = {}
    proof_signatures: dict[str, str] = {}
    for name in REQUIRED_PROOFS:
        fact = signed_facts[name]
        authority = authorities[name]
        if (type(fact) is not SignedFact or type(authority) is not TrustedAuthority
                or type(authority.issuer) is not str or not authority.issuer
                or type(authority.key_id) is not str or not authority.key_id
                or type(authority.secret) is not bytes or len(authority.secret) < 32
                or authority.secret == reviewer_key
                or (authority.issuer, authority.key_id) in tags
                or authority.secret in keys):
            raise HandoffRejected("missing independent pinned source and key for " + name)
        keys.add(authority.secret)
        tags.add((authority.issuer, authority.key_id))
        if (fact.name != name or fact.issuer != authority.issuer
                or fact.key_id != authority.key_id or fact.subject != order_ref
                or fact.buyer_id != buyer_id or fact.passed is not True
                or not _valid_digest(fact.evidence_sha256)
                or type(fact.checked_at) is not int
                or type(fact.valid_until) is not int
                or not fact.checked_at <= now < fact.valid_until
                or not 0 < fact.valid_until - fact.checked_at <= _MAX_LIFETIME_SEC):
            raise HandoffRejected("invalid scoped, timed or purchaser-bound fact " + name)
        _verify_signature(fact, _C_FACT_SCOPE, authority.secret)
        facts[name] = TrustedFact(
            source=authority.issuer + ":" + authority.key_id,
            subject=order_ref, passed=True,
            evidence_sha256=fact.evidence_sha256,
            checked_at=fact.checked_at, valid_until=fact.valid_until,
        )
        trusted_sources[name] = facts[name].source
        proof_signatures[name] = fact.signature_hex
    candidate = Enrollment(
        enrollment_id=order_ref, buyer_id=buyer_id, product=PRODUCT,
        contract_version=VERSION, signed_terms_sha256=independent_terms_sha256,
        network=NETWORK, amount_sun=AMOUNT_SUN, status="approved",
    )
    try:
        boundary = authorize_candidate(
            candidate, facts, expected_terms_sha256=independent_terms_sha256,
            trusted_sources=trusted_sources, now=now,
        )
    except InvoiceBoundaryRejected as exc:
        raise HandoffRejected("C authorization boundary rejected trusted snapshot") from exc
    audit = sha256(json.dumps(
        {"scope": "mojprop.plan1.c.nonpayable-handoff.v1",
         "order_ref": order_ref, "review_sha256": review_hash,
         "proof_signatures": proof_signatures, "terms_sha256": independent_terms_sha256},
        sort_keys=True, separators=(",", ":"),
    ).encode("ascii")).hexdigest()
    if any(boundary.get(key) is not False for key in ("payable", "wallet_request", "credit", "settled")):
        raise HandoffRejected("prior boundary unexpectedly enabled commerce")
    return {
        "schema": "mojprop.plan1.c.nonpayable-handoff.v1",
        "status": "PREPURCHASE_REVIEW_ONLY",
        "order_ref": order_ref,
        "product": PRODUCT,
        "network": NETWORK,
        "amount_sun": AMOUNT_SUN,
        "contract_version": VERSION,
        "review_sha256": review_hash,
        "audit_sha256": audit,
        "independently_signed_proof_count": len(facts),
        "payment_invoice_created": False,
        "payable": False,
        "wallet_request": False,
        "customer_credit": False,
        "chain_finality_verified": False,
        "global_txid_ledger_committed": False,
        "enrollment_created": False,
        "challenge_activated": False,
        "customer_receipt_signed": False,
        "refund_executed": False,
    }

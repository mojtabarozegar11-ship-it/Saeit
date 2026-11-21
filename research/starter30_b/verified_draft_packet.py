"""Starter30: evidence-bound, NON-PAYABLE draft packet verification.

Only the already-approved, independently operated verification office may
create the HMAC attestation using a server-held 256-bit key. The source code
cannot independently determine legal merchant status, buyer identity, real
consent, authenticity of the underlying signatures, wallet custody or payments.
No buyer PII, wallet, RPC, checkout, database mutation or email is handled.
NEVER enable live invoicing using this module or a caller-supplied verifier key.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re

SCHEMA = "mojprop.starter30.reviewed-draft.v1"
SKU = "MOJPROP-STARTER30"
SCOPE = "educational_10_session_simulated_risk_journal_scorecard_feedback"
MERCHANT = "mojplaywin-store"
DOMAIN = "mojplaywin.com"
NETWORK = "tron-mainnet"
AMOUNT_SUN = 30_000_000
MAX_TTL_SEC = 86_400
# The signer MUST be a trusted back-office evidence verification service.
# Production key provisioning and approval are intentionally NOT implemented.
_REQUIRED = frozenset({
    "schema", "order_ref", "lead_token", "request_ref", "attestation_ref",
    "sku", "scope", "merchant_id", "merchant_domain", "network",
    "amount_sun", "buyer_intent", "contract_sha256", "terms_sha256",
    "consent_record_sha256", "buyer_identity_proof_sha256",
    "seller_legal_proof_sha256", "buyer_signature_proof_sha256",
    "seller_signature_proof_sha256", "consent_at_sec",
    "buyer_signed_at_sec", "seller_signed_at_sec", "reviewed_at_sec",
    "issued_at_sec", "expires_at_sec",
})
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_ORDER = re.compile(r"MOJPROP30-[A-Z0-9]{12,32}\Z")
_TOKEN = re.compile(r"LEAD-[A-Z0-9]{16,32}\Z")
_REF = re.compile(r"[A-Z][A-Z0-9-]{11,47}\Z")


class EvidenceGateClosed(ValueError):
    """Evidence failed; do not issue an invoice, grant access or request funds."""


@dataclass(frozen=True)
class ReviewedNonPayableDraft:
    order_ref: str
    attestation_ref: str
    sku: str
    merchant_id: str
    network: str
    amount_sun: int
    scope: str
    issued_at_sec: int
    expires_at_sec: int
    evidence_packet_sha256: str
    status: str = "draft_non_payable"
    payable: bool = False
    receipt_validated: bool = False
    seller_legal_status_proven_by_this_code: bool = False
    signatures_authentic_by_this_code: bool = False
    requires_database_unique_order_and_attestation: bool = True
    requires_external_legal_and_identity_review: bool = True


def _require(test: bool, message: str) -> None:
    if not test:
        raise EvidenceGateClosed(message)


def _canonical(payload: dict) -> bytes:
    # A finite, exact-key, printable-ASCII-only envelope prevents ambiguous
    # Unicode normalization, unrecognized keys and serialization drift.
    _require(type(payload) is dict and set(payload) == _REQUIRED,
             "unexpected/missing attestation fields")
    for key, value in payload.items():
        _require(type(key) is str and key.isascii(), "invalid evidence key")
        _require(type(value) in (str, int), f"unsupported evidence type: {key}")
        if type(value) is str:
            _require(value.isascii() and value.isprintable() and 0 < len(value) <= 160,
                     f"unsafe or oversized evidence: {key}")
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")
    _require(len(body) <= 8192, "evidence packet too large")
    return body


def prepare_reviewed_nonpayable_draft(
    *, payload: dict, attestation_hmac_hex: str, trusted_verifier_key: bytes,
    expected_order_ref: str, expected_lead_token: str, expected_request_ref: str,
    now_sec: int,
) -> ReviewedNonPayableDraft:
    """Authenticate an external review attestation and return ONLY a private draft.

    The key and three expected identifiers must come from separately verified,
    server-controlled records, NEVER browser/form inputs. Even a valid HMAC
    does not establish the underlying review was performed lawfully.
    Durable order/attestation uniqueness and merchant licensing are upstream
    requirements, not solved by this pure function.
    """
    body = _canonical(payload)
    _require(type(trusted_verifier_key) is bytes and len(trusted_verifier_key) >= 32,
             "server-held verifier key missing")
    _require(type(attestation_hmac_hex) is str
             and _HEX64.fullmatch(attestation_hmac_hex) is not None,
             "invalid attestation authentication tag")
    expected_tag = hmac.new(trusted_verifier_key, body, hashlib.sha256).hexdigest()
    _require(hmac.compare_digest(expected_tag, attestation_hmac_hex),
             "attestation authentication failed")

    _require(type(expected_order_ref) is str and _ORDER.fullmatch(expected_order_ref) is not None,
             "expected canonical order required")
    _require(type(expected_lead_token) is str and _TOKEN.fullmatch(expected_lead_token) is not None,
             "expected canonical lead required")
    _require(type(expected_request_ref) is str and _REF.fullmatch(expected_request_ref) is not None,
             "expected real request reference required")
    _require(payload["order_ref"] == expected_order_ref
             and payload["lead_token"] == expected_lead_token
             and payload["request_ref"] == expected_request_ref,
             "attestation does not belong to this order, lead and request")
    _require(_ORDER.fullmatch(payload["order_ref"]) is not None
             and _TOKEN.fullmatch(payload["lead_token"]) is not None
             and _REF.fullmatch(payload["request_ref"]) is not None
             and _REF.fullmatch(payload["attestation_ref"]) is not None,
             "invalid reference format")

    fixed = {"schema": SCHEMA, "sku": SKU, "scope": SCOPE,
             "merchant_id": MERCHANT, "merchant_domain": DOMAIN,
             "network": NETWORK, "amount_sun": AMOUNT_SUN,
             "buyer_intent": "requested_one_time_educational_service_and_terms"}
    for key, value in fixed.items():
        _require(type(payload[key]) is type(value) and payload[key] == value,
                 f"wrong Starter30 scope, units or merchant: {key}")
    for key in ("contract_sha256", "terms_sha256", "consent_record_sha256",
                "buyer_identity_proof_sha256", "seller_legal_proof_sha256",
                "buyer_signature_proof_sha256", "seller_signature_proof_sha256"):
        _require(type(payload[key]) is str and _HEX64.fullmatch(payload[key]) is not None,
                 f"documented evidence hash missing: {key}")
        _require(payload[key] != "0" * 64, f"placeholder hash prohibited: {key}")

    stamps = ("consent_at_sec", "buyer_signed_at_sec", "seller_signed_at_sec",
              "reviewed_at_sec", "issued_at_sec", "expires_at_sec")
    for key in stamps:
        _require(type(payload[key]) is int and payload[key] >= 1_735_689_600,
                 f"invalid timestamp: {key}")
    _require(type(now_sec) is int and now_sec >= 1_735_689_600,
             "trusted server time required")
    consent, buyer_sign, seller_sign, review, issued, expiry = (
        payload[k] for k in stamps
    )
    _require(consent <= buyer_sign <= review and seller_sign <= review <= issued,
             "consent, signatures and review must precede issue")
    _require(0 < expiry - issued <= MAX_TTL_SEC,
             "draft lifetime exceeds 24 hours or is empty")
    _require(issued <= now_sec < expiry, "draft is future-issued or expired")
    _require(issued - consent <= 30 * 86_400,
             "consent is stale for this educational inquiry")

    return ReviewedNonPayableDraft(
        order_ref=expected_order_ref, attestation_ref=payload["attestation_ref"],
        sku=SKU, merchant_id=MERCHANT,
        network=NETWORK, amount_sun=AMOUNT_SUN, scope=SCOPE,
        issued_at_sec=issued, expires_at_sec=expiry,
        evidence_packet_sha256=hashlib.sha256(body).hexdigest(),
    )

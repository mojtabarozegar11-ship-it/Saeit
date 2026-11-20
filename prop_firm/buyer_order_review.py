"""MOJ-PROP-01: cryptographically bound PRIVATE applicant order review.

No payable invoice, customer contact, KYC collection, enrollment, settlement,
broker account, funded capital or publication is provided. A trusted reviewer
must hold the HMAC key separately; caller-supplied keys do not establish trust.
All inputs are anonymous proof references, NEVER identity documents/PII.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import re

from .order_readiness import REQUIRED, SKU, TERMS_VERSION, FEE_TRX, assess_plan_one
from .plans import plan_for_code

SCHEMA = "mojprop.plan1.private-review.v1"
PURPOSE = "requested_two_phase_simulated_prop_challenge_not_starter30"
REF = re.compile(r"[A-Z][A-Z0-9-]{11,63}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
TAG = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_PROOFS = (
    "buyer_identity_proof_sha256", "buyer_age_country_proof_sha256",
    "seller_legal_proof_sha256", "buyer_specific_request_sha256",
    "privacy_consent_sha256", "kyc_review_sha256", "contract_pdf_sha256",
    "buyer_signature_proof_sha256", "seller_signature_proof_sha256",
    "refund_rights_disclosure_sha256", "simulation_and_funding_disclosure_sha256",
    "advertising_law_review_sha256", "capital_reserve_proof_sha256",
    "broker_authorization_sha256", "authorized_reviewer_proof_sha256",
)
REQUIRED_KEYS = frozenset((
    "schema", "purpose", "request_ref", "buyer_ref", "seller_ref",
    "contract_version", "sku", "native_fee_sun", "inquiry_intent_sha256",
    "funded_tier_usd", "evaluation_phase_count", "duration_days",
    "min_distinct_closed_positions", "min_trading_days_per_phase",
    "profit_share_trader_pct", "profit_share_company_pct",
    "simulated_evaluation", "real_account_only_after_pass_and_funding",
    "owner_personal_social_accounts_excluded",
    "social_posts_per_platform", "social_posting_is_conditional_on_law",
    "facts", "proofs", "requested_at_sec", "reviewed_at_sec",
    "expires_at_sec",
))
FIXED = {
    "schema": SCHEMA,
    "purpose": PURPOSE,
    "contract_version": TERMS_VERSION,
    "sku": SKU,
    "native_fee_sun": 30_000_000,
    "funded_tier_usd": 100,
    "evaluation_phase_count": 2,
    "duration_days": 28,
    "min_distinct_closed_positions": 50,
    "min_trading_days_per_phase": 6,
    "profit_share_trader_pct": 70,
    "profit_share_company_pct": 30,
    "simulated_evaluation": True,
    "real_account_only_after_pass_and_funding": True,
    "owner_personal_social_accounts_excluded": True,
    "social_posts_per_platform": 1,
    "social_posting_is_conditional_on_law": True,
}


class Plan1OrderGateClosed(ValueError):
    """No enrollment, payable invoice, capital promise or customer contact."""


def _require(cond: bool, why: str) -> None:
    if not cond:
        raise Plan1OrderGateClosed(why)


def _canonical(payload: dict) -> bytes:
    _require(type(payload) is dict and set(payload) == REQUIRED_KEYS,
             "review packet has extra or missing fields")
    # Nested fields are strictly typed, finite and bounded; json.dumps rejects NaN.
    _require(type(payload["facts"]) is dict
             and set(payload["facts"]) == set(REQUIRED),
             "20 named independent evidence decisions required")
    _require(type(payload["proofs"]) is dict
             and set(payload["proofs"]) == set(REQUIRED_PROOFS),
             "15 independent document-digest slots required")
    _require(all(type(v) is bool for v in payload["facts"].values()),
             "no truthy strings/integers for professional review decisions")
    _require(all(type(v) is str and SHA256.fullmatch(v) is not None
                 and v != "0" * 64 for v in payload["proofs"].values()),
             "missing or placeholder evidence digest")
    for key, value in payload.items():
        if type(value) is str:
            _require(value.isascii() and value.isprintable() and
                     0 < len(value) <= 160, f"invalid {key}")
        elif type(value) not in (bool, int, dict):
            raise Plan1OrderGateClosed(f"invalid type for {key}")
    out = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     allow_nan=False, ensure_ascii=True).encode("ascii")
    _require(len(out) <= 8192, "review packet too large")
    return out


@dataclass(frozen=True)
class PrivateOrderCase:
    request_ref: str
    buyer_ref: str
    seller_ref: str
    sku: str
    contract_version: str
    native_fee_sun: int
    verified_fact_count: int
    review_packet_sha256: str
    inquiry_intent_sha256: str
    expires_at_sec: int
    stage: str = "private_review_only"
    payable_invoice_created: bool = False
    challenge_enrollment_created: bool = False
    settlement_confirmed: bool = False
    funding_proven_by_this_code: bool = False
    social_post_published: bool = False
    requires_external_legal_kyc_funding_review: bool = True


def evaluate_signed_plan1_request(
    *, packet: dict, signed_tag_hex: str, trusted_reviewer_key: bytes,
    expected_request_ref: str, expected_buyer_ref: str,
    expected_seller_ref: str, expected_inquiry_intent_sha256: str,
    server_now_sec: int,
) -> PrivateOrderCase:
    """Review ONLY a signed, already independently checked buyer request.

    The key, expected IDs and trusted clock MUST originate from secure internal
    components, never from a browser. HMAC only proves envelope integrity; it
    does not verify that the referenced external KYC/contract/capital exists.
    """
    body = _canonical(packet)
    _require(type(trusted_reviewer_key) is bytes and
             len(trusted_reviewer_key) >= 32, "trusted internal reviewer required")
    _require(type(signed_tag_hex) is str and TAG.fullmatch(signed_tag_hex)
             is not None, "signed review tag missing")
    tag = hmac.new(trusted_reviewer_key, body, "sha256").hexdigest()
    _require(hmac.compare_digest(signed_tag_hex, tag),
             "review signature mismatch")
    for field, expected in (
        ("request_ref", expected_request_ref), ("buyer_ref", expected_buyer_ref),
        ("seller_ref", expected_seller_ref),
    ):
        _require(type(expected) is str and REF.fullmatch(expected) is not None
                 and packet[field] == expected, f"untrusted {field} binding")
    _require(type(expected_inquiry_intent_sha256) is str and
             SHA256.fullmatch(expected_inquiry_intent_sha256) is not None,
             "server-trusted inquiry digest required")
    _require(type(packet["inquiry_intent_sha256"]) is str and
             packet["inquiry_intent_sha256"] == expected_inquiry_intent_sha256,
             "signed review must match the original buyer inquiry digest")
    for field, expected in FIXED.items():
        _require(type(packet[field]) is type(expected)
                 and packet[field] == expected,
                 f"wrong Plan 1 policy or simulated-disclosure: {field}")
    plan = plan_for_code(SKU)
    _require(plan.entry_fee_trx == FEE_TRX and
             plan.starting_capital_usd == 100 and
             plan.min_trading_days_per_stage == 6 and
             plan.minimum_verified_closed_trades == 50 and
             plan.duration_days == 28,
             "canonical Plan 1 policy drift")
    _require(assess_plan_one(packet["facts"]).eligible,
             "independent readiness checks are incomplete")
    for field in ("requested_at_sec", "reviewed_at_sec", "expires_at_sec"):
        _require(type(packet[field]) is int and
                 packet[field] >= 1_735_689_600,
                 f"invalid trusted timestamp: {field}")
    _require(type(server_now_sec) is int and
             server_now_sec >= 1_735_689_600, "trusted server clock required")
    request, reviewed, expires = (
        packet["requested_at_sec"], packet["reviewed_at_sec"],
        packet["expires_at_sec"],
    )
    _require(request <= reviewed <= server_now_sec < expires,
             "expired, unreviewed or future-dated applicant request")
    _require(0 < expires - reviewed <= 86_400,
             "private review window must be at most 24 hours")
    _require(reviewed - request <= 30 * 86_400,
             "stale customer inquiry; seek fresh informed consent")
    # No transferable entitlement or invoice ID is created. A later,
    # separately reviewed atomic database workflow must enforce uniqueness.
    return PrivateOrderCase(
        request_ref=expected_request_ref, buyer_ref=expected_buyer_ref,
        seller_ref=expected_seller_ref, sku=SKU,
        contract_version=TERMS_VERSION, native_fee_sun=30_000_000,
        verified_fact_count=len(REQUIRED),
        review_packet_sha256=sha256(body).hexdigest(),
        inquiry_intent_sha256=expected_inquiry_intent_sha256,
        expires_at_sec=expires,
    )

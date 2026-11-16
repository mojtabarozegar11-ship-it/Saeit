"""Read-only consent-to-private-review bridge for canonical PropInterest.

This module intentionally does NOT query or mutate the ORM. An authenticated
CRM adapter must supply the actual DB row AND a separately signed provenance
attestation from the intake registry. Email is NEVER copied into output.
A CRM row by itself does not prove a person's identity, opt-in or payment.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re

from .buyer_interest_form import UnverifiedInquiry
from .buyer_order_review import Plan1OrderGateClosed
from .order_readiness import SKU, TERMS_VERSION

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_REF = re.compile(r"REQUEST-[A-Z0-9]{16,32}\Z")
_LANG = frozenset(("en", "fa", "ar"))
_CONSENT_VERSION = "moj-prop-interest-v1"


@dataclass(frozen=True)
class PrivateInterestLink:
    """No email, no KYC document, no address, no invoice or enrollment."""
    canonical_interest_pk: int
    request_ref: str
    inquiry_sha256: str
    consent_evidence_sha256: str
    sku: str = SKU
    terms_version: str = TERMS_VERSION
    state: str = "CONSENT_LINK_PRIVATE_REVIEW_ONLY"
    email_disclosed: bool = False
    kyc_proven: bool = False
    payable: bool = False
    buyer_contact_authorized_by_this_module: bool = False
    enrollment_created: bool = False


def bind_canonical_interest_to_private_inquiry(
    *, canonical_interest: dict, inquiry: UnverifiedInquiry,
    trusted_consent_attestation: dict, signed_consent_tag_hex: str,
    trusted_consent_key: bytes, expected_request_ref: str,
    expected_interest_pk: int, expected_inquiry_sha256: str,
    expected_consent_evidence_sha256: str,
) -> PrivateInterestLink:
    """Validate consent lineage without converting interest into commerce.

    canonical_interest is a read-only snapshot of PropInterest, including
    email only to establish that a nonempty valid-looking record exists.
    Its address is NEVER included in HMAC material, output, logs or errors.
    The separately held consent registry must bind exact row PK, request,
    inquiry digest, consent evidence digest, product, version and opt-in scope.
    No synthetic signature is accepted as legal proof in production.
    """
    if type(inquiry) is not UnverifiedInquiry:
        raise Plan1OrderGateClosed("original inquiry unavailable")
    if (type(expected_request_ref) is not str
            or _REF.fullmatch(expected_request_ref) is None
            or inquiry.request_ref != expected_request_ref
            or inquiry.sku != SKU or inquiry.terms_version != TERMS_VERSION
            or inquiry.state != "unverified_private_interest"
            or any(getattr(inquiry, k) is not False for k in (
                "allowed_to_contact", "payment_allowed",
                "challenge_enrollment_allowed", "kyc_verified",
                "customer_contract_executed", "marketing_opt_in",
            ))):
        raise Plan1OrderGateClosed("private inquiry scope invalid")
    if (type(expected_interest_pk) is not int or expected_interest_pk <= 0
            or type(expected_inquiry_sha256) is not str
            or _HEX.fullmatch(expected_inquiry_sha256) is None
            or inquiry.anonymous_intent_sha256 != expected_inquiry_sha256
            or type(expected_consent_evidence_sha256) is not str
            or _HEX.fullmatch(expected_consent_evidence_sha256) is None
            or expected_consent_evidence_sha256 == "0"*64):
        raise Plan1OrderGateClosed("trusted record identity absent")
    if type(canonical_interest) is not dict or set(canonical_interest) != {
        "id", "email", "plan_code", "consent_version", "source_language", "status",
    }:
        raise Plan1OrderGateClosed("canonical PropInterest snapshot required")
    email = canonical_interest["email"]
    if (type(email) is not str or not 3 <= len(email) <= 254
            or "@" not in email or any(c.isspace() for c in email)
            or canonical_interest["id"] != expected_interest_pk
            or type(canonical_interest["id"]) is not int
            or canonical_interest["plan_code"] != SKU
            or canonical_interest["consent_version"] != _CONSENT_VERSION
            or canonical_interest["source_language"] not in _LANG
            or canonical_interest["status"] != "new"):
        raise Plan1OrderGateClosed("canonical consent row ineligible or withdrawn")
    if (type(trusted_consent_key) is not bytes or len(trusted_consent_key) < 32
            or type(signed_consent_tag_hex) is not str
            or _HEX.fullmatch(signed_consent_tag_hex) is None):
        raise Plan1OrderGateClosed("independent consent registry signature missing")
    if type(trusted_consent_attestation) is not dict:
        raise Plan1OrderGateClosed("trusted consent registry attestation missing")
    expected = {
        "purpose": "mojprop-plan1-optin-lineage-v1",
        "interest_pk": expected_interest_pk,
        "request_ref": expected_request_ref,
        "inquiry_sha256": expected_inquiry_sha256,
        "consent_evidence_sha256": expected_consent_evidence_sha256,
        "sku": SKU,
        "terms_version": TERMS_VERSION,
        "consent_version": _CONSENT_VERSION,
        "contact_scope": "buyer_requested_one_to_one_plan1_review_only",
        "withdrawn": False,
    }
    if trusted_consent_attestation != expected:
        raise Plan1OrderGateClosed("independent consent scope or lineage mismatch")
    canonical = json.dumps(expected, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True).encode("ascii")
    correct = hmac.new(trusted_consent_key, canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(correct, signed_consent_tag_hex):
        raise Plan1OrderGateClosed("consent registry provenance signature invalid")
    return PrivateInterestLink(
        canonical_interest_pk=expected_interest_pk,
        request_ref=expected_request_ref,
        inquiry_sha256=expected_inquiry_sha256,
        consent_evidence_sha256=expected_consent_evidence_sha256,
    )

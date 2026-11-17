"""Verify a Plan 1 buyer inquiry was issued by the protected intake service.

SOURCE-ONLY, NO HTTP / KYC / DB / PAYMENT SIDE EFFECTS.
The private HMAC key must be provisioned by an independently authenticated
server-side intake service, never the browser. A successful MAC does NOT
establish verified age, permitted jurisdiction, legal consent, or paid status.
The issuer's one-use request registry and revocation list remain external.
"""
from __future__ import annotations

from dataclasses import fields
import hashlib
import hmac
import json
import re

from .buyer_interest_form import UnverifiedInquiry
from .buyer_order_review import Plan1OrderGateClosed
from .order_readiness import SKU, TERMS_VERSION

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_TAG = re.compile(r"[0-9a-f]{64}\Z")
_REQUEST = re.compile(r"REQUEST-[A-Z0-9]{16,32}\Z")
_COUNTRY = re.compile(r"[A-Z]{2}\Z")


def verify_server_issued_private_inquiry(
    *, inquiry: UnverifiedInquiry, signed_intake_hmac_hex: str,
    trusted_intake_key: bytes, expected_request_ref: str,
    expected_inquiry_digest: str,
) -> None:
    """Verify source authentication only: never elevate an inquiry to KYC.

    Binds exactly the immutable dataclass fields and request/digest to an
    independent server-held intake key. No auth key is generated here.
    """
    if type(inquiry) is not UnverifiedInquiry:
        raise Plan1OrderGateClosed("authenticated original inquiry required")
    if (type(trusted_intake_key) is not bytes or len(trusted_intake_key) < 32):
        raise Plan1OrderGateClosed("independently held intake HMAC key missing")
    if (type(signed_intake_hmac_hex) is not str
            or _TAG.fullmatch(signed_intake_hmac_hex) is None):
        raise Plan1OrderGateClosed("intake authentication tag missing")
    if (type(expected_request_ref) is not str
            or _REQUEST.fullmatch(expected_request_ref) is None
            or inquiry.request_ref != expected_request_ref):
        raise Plan1OrderGateClosed("intake request identity mismatch")
    if (type(expected_inquiry_digest) is not str
            or _DIGEST.fullmatch(expected_inquiry_digest) is None
            or inquiry.anonymous_intent_sha256 != expected_inquiry_digest):
        raise Plan1OrderGateClosed("intake source digest mismatch")
    if (inquiry.sku != SKU or inquiry.terms_version != TERMS_VERSION
            or inquiry.state != "unverified_private_interest"
            or type(inquiry.declared_country) is not str
            or _COUNTRY.fullmatch(inquiry.declared_country) is None):
        raise Plan1OrderGateClosed("intake identity and stage invalid")
    if any(type(getattr(inquiry, k)) is not bool
           or getattr(inquiry, k) is not False
           for k in (
               "legal_country_verified",
               "age_independently_verified",
               "kyc_verified",
               "customer_contract_executed",
               "marketing_opt_in",
               "allowed_to_contact",
               "payment_allowed",
               "challenge_enrollment_allowed",
           )):
        raise Plan1OrderGateClosed("unverified inquiry cannot claim authorizations")
    body = {field.name: getattr(inquiry, field.name) for field in fields(UnverifiedInquiry)}
    if any(type(v) not in (str, bool) for v in body.values()):
        raise Plan1OrderGateClosed("unsafe inquiry dataclass value")
    if any(not v.isascii() or not v.isprintable() or not 1 <= len(v) <= 200
           for v in body.values() if type(v) is str):
        raise Plan1OrderGateClosed("unsafe intake string")
    canonical = json.dumps(
        {"purpose": "mojprop-plan1-server-intake-v1", "inquiry": body},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode("ascii")
    if len(canonical) > 2048:
        raise Plan1OrderGateClosed("oversized intake authentication payload")
    expected_mac = hmac.new(
        trusted_intake_key, canonical, hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_mac, signed_intake_hmac_hex):
        raise Plan1OrderGateClosed("intake source authentication failed")
    # Does not claim request uniqueness, buyer age, KYC or lawful contact.

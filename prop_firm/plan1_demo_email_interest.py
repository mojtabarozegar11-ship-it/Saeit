"""MOJ-PROP-01: verified-email *interest*, not KYC or a financial order.

This B-owned pure adapter consumes the EXISTING canonical consent link and a
separately HMAC-authenticated, short-lived OTP verification receipt. It never
issues email, creates a form or a second lead, reads customer PII, performs
identity checks, opens demo/real accounts, signs contracts or invoices buyers.

A self-declared country and adult-age statement are NOT proof of jurisdiction
or age. Applicable legal purchase-level screening remains independent from
broker live-account KYC, which belongs only to post-two-demo-pass promotion.
"""
from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import re

from .buyer_order_review import Plan1OrderGateClosed
from .order_readiness import SKU, TERMS_VERSION
from .plan1_canonical_interest_bridge import PrivateInterestLink

OTP_SCHEMA = "mojprop.plan1.email-interest.otp-proof.v1"
OTP_PURPOSE = "single_plan1_private_demo_interest_no_purchase"
OTP_FIELDS = frozenset((
    "schema", "purpose", "interest_pk", "request_ref", "inquiry_sha256",
    "sku", "terms_version", "email_control_verified", "issued_at_sec",
    "expires_at_sec",
))
COUNTRY = re.compile(r"[A-Z]{2}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
MAX_OTP_LIFETIME_SEC = 600
MIN_EPOCH = 1735689600


@dataclass(frozen=True)
class VerifiedDemoInterest:
    """Private no-PII nonpayable preview only; never legal buyer clearance."""
    interest_pk: int
    request_ref: str
    sku: str
    terms_version: str
    declared_country: str
    email_otp_receipt_digest: str
    email_control_attested_by_trusted_otp_service: bool = True
    age_18_self_attested_not_verified: bool = True
    country_self_declared_not_verified: bool = True
    two_challenge_phases_simulated: bool = True
    live_litefinance_account_required_for_demo: bool = False
    live_broker_kyc_required_for_demo_as_such: bool = False
    purchase_legality_verified: bool = False
    buyer_legal_age_verified: bool = False
    buyer_country_legally_permitted: bool = False
    actual_kyc_verified: bool = False
    buyer_signed_contract_verified: bool = False
    merchant_funding_verified: bool = False
    marketing_consent: bool = False
    contact_permission_created: bool = False
    payable_invoice: bool = False
    payment_authorized: bool = False
    demo_account_activated: bool = False
    real_account_activated: bool = False
    stage: str = "PRIVATE_EMAIL_VERIFIED_INTEREST_ONLY"


def review_existing_demo_interest_otp(
    *, consent_link, signed_otp_receipt, otp_tag_hex,
    trusted_otp_service_key, trusted_consent_service_key,
    declared_country, age_18_self_attested, server_now_sec,
):
    """Verify server HMAC envelope without inventing verified customer identity.

    OTP service must independently check the email control and consume/replay
    protect OTPs in its own durable authority, not via browser flags alone.
    A successful HMAC confirms envelope integrity, NOT regulatory KYC.
    """
    if (type(consent_link) is not PrivateInterestLink
            or consent_link.state != "CONSENT_LINK_PRIVATE_REVIEW_ONLY"
            or consent_link.sku != SKU
            or consent_link.terms_version != TERMS_VERSION
            or type(consent_link.canonical_interest_pk) is not int
            or consent_link.canonical_interest_pk <= 0
            or type(consent_link.inquiry_sha256) is not str
            or DIGEST.fullmatch(consent_link.inquiry_sha256) is None
            or any(getattr(consent_link, flag) is not False for flag in (
                "payable", "enrollment_created", "kyc_proven",
                "buyer_contact_authorized_by_this_module",
                "email_disclosed",
            ))):
        raise Plan1OrderGateClosed("canonical nonpayable consent lineage required")
    if (type(declared_country) is not str
            or COUNTRY.fullmatch(declared_country) is None
            or age_18_self_attested is not True):
        raise Plan1OrderGateClosed("exact prospective adult/country declarations required")
    if (type(trusted_otp_service_key) is not bytes
            or type(trusted_consent_service_key) is not bytes
            or len(trusted_otp_service_key) < 32
            or len(trusted_consent_service_key) < 32
            or hmac.compare_digest(trusted_otp_service_key,
                                   trusted_consent_service_key)):
        raise Plan1OrderGateClosed("independent trusted OTP and consent authorities required")
    if (type(otp_tag_hex) is not str or DIGEST.fullmatch(otp_tag_hex) is None
            or type(signed_otp_receipt) is not dict
            or set(signed_otp_receipt) != OTP_FIELDS):
        raise Plan1OrderGateClosed("exact signed private OTP evidence required")
    expected = {
        "schema": OTP_SCHEMA, "purpose": OTP_PURPOSE,
        "interest_pk": consent_link.canonical_interest_pk,
        "request_ref": consent_link.request_ref,
        "inquiry_sha256": consent_link.inquiry_sha256,
        "sku": SKU, "terms_version": TERMS_VERSION,
        "email_control_verified": True,
    }
    for key, value in expected.items():
        if type(signed_otp_receipt[key]) is not type(value) or signed_otp_receipt[key] != value:
            raise Plan1OrderGateClosed("signed email-control evidence does not bind the consent record")
    issued = signed_otp_receipt["issued_at_sec"]
    expiry = signed_otp_receipt["expires_at_sec"]
    if (type(issued) is not int or type(expiry) is not int
            or type(server_now_sec) is not int
            or issued < MIN_EPOCH or issued > server_now_sec
            or not issued <= server_now_sec < expiry
            or expiry - issued > MAX_OTP_LIFETIME_SEC):
        raise Plan1OrderGateClosed("expired, replayable or untrusted OTP receipt timing")
    body = json.dumps(signed_otp_receipt, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(body) > 4096:
        raise Plan1OrderGateClosed("oversized or invalid email-control envelope")
    expected_tag = hmac.new(trusted_otp_service_key, body, sha256).hexdigest()
    if not hmac.compare_digest(expected_tag, otp_tag_hex):
        raise Plan1OrderGateClosed("independent OTP evidence signature mismatch")
    return VerifiedDemoInterest(
        interest_pk=consent_link.canonical_interest_pk,
        request_ref=consent_link.request_ref,
        sku=SKU, terms_version=TERMS_VERSION,
        declared_country=declared_country,
        email_otp_receipt_digest=sha256(body).hexdigest(),
    )

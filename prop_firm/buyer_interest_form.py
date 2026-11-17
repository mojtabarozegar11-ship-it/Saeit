"""MOJ-PROP-01 applicant interest form: source-only, no PII or payments.

Not an order, a KYC service, a lawful customer contract or an email lead.
New private inquiries explicitly acknowledge the no-buyer-posting waiver and
legally necessary purchase screening; LIVE BROKER KYC is not a condition to
request information or start either demo assessment. Previously signed HMAC
intents are preserved as historical records, never silently upgraded.
Actual names, contacts, identity docs and approval country registry require a
separate secured backend and independently reviewed privacy/legal basis.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re

from .order_readiness import SKU, TERMS_VERSION

COUNTRY_CODE = re.compile(r"[A-Z]{2}\Z")
REQUEST_REF = re.compile(r"REQUEST-[A-Z0-9]{16,32}\Z")
_REQUIRED = frozenset((
    "request_ref", "sku", "terms_version", "self_declared_country",
    "age_at_least_18_self_attested", "contact_for_this_inquiry_requested",
    "ack_native_30_trx", "ack_evaluation_is_simulated",
    "ack_two_phases_28_days", "ack_50_positions_6_days_per_phase",
    "ack_real_100_usd_funding_is_conditional",
    "ack_70_30_only_on_eligible_funded_profit",
    "ack_no_buyer_social_posts_required",
    "ack_no_access_to_owner_social_accounts",
    "ack_legal_purchase_screening_if_required",
    "ack_refund_policy_requires_legal_review",
    "ack_terms_can_be_reviewed_before_payment",
    "ack_privacy_and_specific_contact_purpose",
))


class InterestFormBlocked(ValueError):
    """The user has not requested an accurate private information review."""


@dataclass(frozen=True)
class UnverifiedInquiry:
    request_ref: str
    sku: str
    terms_version: str
    declared_country: str
    received_at: str
    anonymous_intent_sha256: str
    state: str = "unverified_private_interest"
    legal_country_verified: bool = False
    age_independently_verified: bool = False
    kyc_verified: bool = False
    customer_contract_executed: bool = False
    marketing_opt_in: bool = False
    allowed_to_contact: bool = False
    payment_allowed: bool = False
    challenge_enrollment_allowed: bool = False


def validate_private_plan1_interest(*, form: dict, server_received_at: datetime) -> UnverifiedInquiry:
    """Validate only explicit product comprehension and purpose-specific request.

    Not intended for direct deployment to public HTTP. Anonymous inquiry
    cannot be used for a marketing campaign or an invoice. Country and age
    declarations are intentionally NOT treated as independently verified.
    """
    if type(form) is not dict or set(form) != _REQUIRED:
        # Historical v1.2 inquiries naming required social posts / live-broker
        # screening are NOT fresh acceptance of the owner's revised policy.
        # Do not silently migrate their consent or rewrite stored intent.
        raise InterestFormBlocked("current no-post, demo-only Plan 1 comprehension required")
    if (type(form["request_ref"]) is not str or
            REQUEST_REF.fullmatch(form["request_ref"]) is None):
        raise InterestFormBlocked("server-issued opaque request reference required")
    if type(form["sku"]) is not str or form["sku"] != SKU:
        raise InterestFormBlocked("wrong product: not an educational report")
    if type(form["terms_version"]) is not str or form["terms_version"] != TERMS_VERSION:
        raise InterestFormBlocked("current Plan 1 terms must be explicitly read")
    country = form["self_declared_country"]
    if type(country) is not str or COUNTRY_CODE.fullmatch(country) is None:
        raise InterestFormBlocked("declared ISO-3166 alpha-2 country required")
    for name in _REQUIRED - {"request_ref", "sku", "terms_version",
                             "self_declared_country"}:
        if type(form[name]) is not bool or form[name] is not True:
            raise InterestFormBlocked(f"explicit comprehension/intent missing: {name}")
    if (type(server_received_at) is not datetime or
            server_received_at.tzinfo is None or
            server_received_at.utcoffset() is None):
        raise InterestFormBlocked("server-owned timezone-aware receipt time required")
    stamp = server_received_at.astimezone(timezone.utc).isoformat()
    serialized = json.dumps(form, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True, allow_nan=False)
    return UnverifiedInquiry(
        request_ref=form["request_ref"], sku=SKU,
        terms_version=TERMS_VERSION, declared_country=country,
        received_at=stamp,
        anonymous_intent_sha256=sha256(serialized.encode("ascii")).hexdigest(),
    )

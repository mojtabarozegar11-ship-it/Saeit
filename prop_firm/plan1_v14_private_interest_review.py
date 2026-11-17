"""Nonpayable, no-PII buyer interest comprehension for PROSPECTIVE MOJ PROP v1.4.1.

An explicit new terms acceptance is required; old buyer_interest_form.py
v1.2 no-post consent MUST NOT be migrated or recycled. This checker cannot
authenticate identity, age, country, a broker, or legal advertising rules.
No storage, network, email, lead generation, checkout or enrollment side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re

from .plan1_v14_social_or_50_terms import review_prospective_terms

REF_PATTERN = re.compile(r"REQUEST-[A-Z0-9]{16,32}\Z")
COUNTRY_PATTERN = re.compile(r"[A-Z]{2}\Z")
ACKNOWLEDGMENTS = frozenset({
    "ack_two_sequential_simulated_phases",
    "ack_fifty_closed_positions_total_not_each_stage",
    "ack_six_trading_days_in_each_stage",
    "ack_28_day_trading_window",
    "ack_one_qualifying_original_instagram_or_facebook_post",
    "ack_post_remains_public_for_at_least_672_hours",
    "ack_social_clock_independent_from_trading_window",
    "ack_required_clear_promotion_relationship_disclosure",
    "ack_no_profit_guarantee_or_misleading_broker_endorsement",
    "ack_social_requirement_subject_to_legal_clearance",
    "ack_30_native_trx_is_evaluation_not_broker_funding",
    "ack_usd100_real_account_not_automatically_funded",
    "ack_signed_contract_and_refund_review_before_payment",
    "ack_age_country_and_kyc_screening_still_required",
    "ack_purpose_specific_privacy_review",
})
REQUIRED_FIELDS = ACKNOWLEDGMENTS | frozenset({
    "request_ref", "sku", "terms_version", "terms_digest_sha256",
    "self_declared_country", "age_at_least_18_self_attested",
    "request_information_only", "marketing_consent",
})


class ProspectiveInterestBlocked(ValueError):
    """Prospective v1.4.1 request cannot proceed even as a private review."""


@dataclass(frozen=True)
class UnverifiedV14Interest:
    request_ref: str
    sku: str
    terms_version: str
    accepted_terms_sha256: str
    declared_country: str
    received_at_utc: str
    redacted_comprehension_sha256: str
    state: str = "prospective_nonpayable_interest_only"
    identity_independently_verified: bool = False
    age_independently_verified: bool = False
    broker_permission_verified: bool = False
    finance_and_advertising_law_cleared: bool = False
    contract_signed: bool = False
    paid_invoice_authorized: bool = False
    enrollment_authorized: bool = False
    real_orders_authorized: bool = False
    automated_marketing_authorized: bool = False


def review_nonpayable_v14_interest(*, form: dict, server_received_at: datetime) -> UnverifiedV14Interest:
    """Strict current contract fingerprint and explicit new buyer comprehension.

    The caller must supply a server-owned request_ref and received_at time.
    This pure function neither authenticates those assertions nor stores PII.
    """
    terms = review_prospective_terms()
    if type(form) is not dict or set(form) != REQUIRED_FIELDS:
        raise ProspectiveInterestBlocked("exact prospective buyer comprehension schema required")
    ref = form["request_ref"]
    if type(ref) is not str or REF_PATTERN.fullmatch(ref) is None:
        raise ProspectiveInterestBlocked("server-issued opaque request reference required")
    if (type(form["sku"]) is not str or form["sku"] != terms.sku
            or type(form["terms_version"]) is not str
            or form["terms_version"] != terms.version
            or type(form["terms_digest_sha256"]) is not str
            or form["terms_digest_sha256"] != terms.contract_candidate_sha256):
        raise ProspectiveInterestBlocked("exact current signed-by-code draft digest required")
    country = form["self_declared_country"]
    if type(country) is not str or COUNTRY_PATTERN.fullmatch(country) is None:
        raise ProspectiveInterestBlocked("two-letter ISO country declaration required")
    if type(form["age_at_least_18_self_attested"]) is not bool or form["age_at_least_18_self_attested"] is not True:
        raise ProspectiveInterestBlocked("explicit adult declaration required")
    if type(form["request_information_only"]) is not bool or form["request_information_only"] is not True:
        raise ProspectiveInterestBlocked("this flow only handles requests for information")
    # A request for plan terms is never automatic consent to advertising.
    if type(form["marketing_consent"]) is not bool or form["marketing_consent"] is not False:
        raise ProspectiveInterestBlocked("marketing must be separate and default-denied")
    for name in ACKNOWLEDGMENTS:
        if type(form[name]) is not bool or form[name] is not True:
            raise ProspectiveInterestBlocked(f"terms acknowledgment missing: {name}")
    if (type(server_received_at) is not datetime or server_received_at.tzinfo is None
            or server_received_at.utcoffset() is None):
        raise ProspectiveInterestBlocked("server-owned timezone-aware request time required")
    stamp = server_received_at.astimezone(timezone.utc).isoformat()
    canonical = json.dumps(form, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
                           allow_nan=False).encode("ascii")
    return UnverifiedV14Interest(
        request_ref=ref, sku=terms.sku, terms_version=terms.version,
        accepted_terms_sha256=terms.contract_candidate_sha256,
        declared_country=country, received_at_utc=stamp,
        redacted_comprehension_sha256=sha256(canonical).hexdigest(),
    )

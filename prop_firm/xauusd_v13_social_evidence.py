"""Offline 28-day Instagram OR Facebook evidence preview for unsigned MOJ-PROP-01 v1.3.

This performs bounded, deterministic consistency checks only. It NEVER visits
social sites, authenticates the submitted evidence, signs customer terms,
issues invoices, collects TRX, starts challenges, or executes trading.
A caller-supplied independent-review flag is NOT actual external attestation.
Historical v1.2 no-post waiver remains unaffected.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .social_policy import aware_utc, valid_platform_post_url
from .xauusd_v13_draft_terms import draft_gold_terms_v13
from .xauusd_v13_preflight import DRAFT_CONTRACT_VERSION

ALLOWED_PLATFORMS = frozenset(("instagram", "facebook"))
DURATION = timedelta(days=28)


@dataclass(frozen=True)
class V13SocialEvidence:
    platform: str
    post_url: str
    posted_at: datetime
    reviewed_at: datetime
    buyer_separately_consented: bool
    operator_claims_independent_review: bool
    original_post_claimed: bool
    continuous_visibility_claimed: bool
    promotion_disclosed_claimed: bool
    no_misleading_profit_claims_claimed: bool
    no_broker_credentials_exposed_claimed: bool


@dataclass(frozen=True)
class V13SocialReview:
    contract_version: str
    proposal_evidence_consistent: bool
    blockers: tuple[str, ...]
    earliest_eligible_review_at: datetime
    # Even mathematically valid submitted evidence cannot authenticate itself.
    external_platform_independently_attested: bool = False
    buyer_signed_terms_independently_proven: bool = False
    social_advertising_legally_approved: bool = False
    payable_checkout_authorized: bool = False
    customer_enrollment_authorized: bool = False
    live_broker_order_authorized: bool = False
    outbound_social_publication_authorized: bool = False


def review_v13_social_proposal(
    evidence: V13SocialEvidence, *, evaluation_started_at: datetime,
    as_of: datetime,
) -> V13SocialReview:
    """One original post on EITHER platform kept visible for 28 days.

    All review booleans are UNTRUSTED claims requiring an external
    evidence-provenance adapter and legal review before customer use.
    The result is never a purchase, qualification, or broker permission.
    """
    if type(evidence) is not V13SocialEvidence:
        raise TypeError("exact immutable review-evidence type required")
    terms = draft_gold_terms_v13()
    if (
        terms.contract_version != DRAFT_CONTRACT_VERSION
        or terms.minimum_posts_on_either_platform != 1
        or terms.continuous_visibility_days != DURATION.days
        or terms.social_legality_independently_approved is not False
        or terms.social_customer_terms_signed is not False
        or terms.checkout_enabled is not False
    ):
        raise RuntimeError("v1.3 proposal/source drift requires review")

    start = aware_utc(evaluation_started_at, "evaluation_started_at")
    now = aware_utc(as_of, "as_of")
    posted = aware_utc(evidence.posted_at, "posted_at")
    reviewed = aware_utc(evidence.reviewed_at, "reviewed_at")
    if now < start:
        raise ValueError("assessment cannot predate challenge start")

    reasons = []
    if evidence.platform not in ALLOWED_PLATFORMS:
        reasons.append("unsupported_platform")
    if not valid_platform_post_url(evidence.post_url, evidence.platform):
        reasons.append("invalid_or_prohibited_post_url")
    if not start <= posted <= start + DURATION:
        reasons.append("post_outside_challenge_window")
    earliest = posted + DURATION
    if reviewed < earliest:
        reasons.append("post_not_reviewed_after_28_days")
    if reviewed > now:
        reasons.append("review_timestamp_is_in_future")
    required_flags = (
        ("buyer_separately_consented", "buyer_post_consent_unverified"),
        ("operator_claims_independent_review", "independent_operator_review_unverified"),
        ("original_post_claimed", "post_originality_unverified"),
        ("continuous_visibility_claimed", "28_day_visibility_unverified"),
        ("promotion_disclosed_claimed", "commercial_disclosure_unverified"),
        ("no_misleading_profit_claims_claimed", "profit_claim_safety_unverified"),
        ("no_broker_credentials_exposed_claimed", "account_privacy_unverified"),
    )
    for field, blocker in required_flags:
        if getattr(evidence, field) is not True:
            reasons.append(blocker)
    return V13SocialReview(
        contract_version=terms.contract_version,
        proposal_evidence_consistent=not reasons,
        blockers=tuple(dict.fromkeys(reasons)),
        earliest_eligible_review_at=earliest,
    )

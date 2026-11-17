"""Fail-closed, nonpayable combined fifty-closed-trade AND social-OR proof.

Explicitly combines the v1.3 two-phase mathematical review with the NEW
prospective v1.4 one-platform/28-day mathematical review. Caller-created
dataclasses are NOT authenticated broker, social-platform or legal evidence.
"""
from __future__ import annotations

from dataclasses import dataclass

from .xauusd_v13_qualification_preview import QualificationPreview
from .plan1_v14_social_or_28d_review import Social28DayReview
from .plan1_v14_social_or_50_terms import review_prospective_terms


@dataclass(frozen=True)
class ProposedV14Qualification:
    draft_contract_version: str
    candidate_terms_sha256: str
    phase_and_fifty_math_satisfied: bool
    social_post_math_satisfied: bool
    full_draft_math_satisfied: bool
    reasons: tuple[str, ...]
    sources_independently_authenticated: bool = False
    platform_post_independently_verified: bool = False
    advertising_legally_approved: bool = False
    signed_customer_contract_verified: bool = False
    paid_enrollment_authorized: bool = False
    real_trading_authorized: bool = False
    payout_authorized: bool = False


def review_v14_combined(*, phases: QualificationPreview,
                        social: Social28DayReview) -> ProposedV14Qualification:
    terms = review_prospective_terms()
    if type(phases) is not QualificationPreview or type(social) is not Social28DayReview:
        raise ValueError("typed upstream mathematical reviews required")
    if (phases.sku != terms.sku
            or phases.contract_version != terms.supersedes_unsigned_draft_version
            or phases.required_closed_positions != terms.closed_trades_total):
        raise ValueError("stale or mismatched phase review")
    phase_ok = (phases.entire_challenge_math_pass is True
                and phases.phase_one_math_pass is True
                and phases.phase_two_math_pass is True
                and phases.reviewed_closed_positions >= terms.closed_trades_total
                and not phases.reasons)
    social_ok = (social.candidate_platform in terms.social_platforms
                 and social.timeline_mathematically_consistent is True
                 and social.observed_hours >= terms.public_post_hours
                 and not social.reasons)
    reasons = []
    if not phase_ok:
        reasons.append("two_phases_or_fifty_reconciled_trades_not_mathematically_proven")
    if not social_ok:
        reasons.append("single_platform_twenty_eight_days_not_mathematically_proven")
    # This is not an identity, contract, marketing, broker or checkout gate.
    return ProposedV14Qualification(
        draft_contract_version=terms.version,
        candidate_terms_sha256=terms.contract_candidate_sha256,
        phase_and_fifty_math_satisfied=phase_ok,
        social_post_math_satisfied=social_ok,
        full_draft_math_satisfied=phase_ok and social_ok,
        reasons=tuple(reasons),
    )

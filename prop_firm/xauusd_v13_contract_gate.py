"""Non-payable v1.3 draft contract consistency audit; never signs terms.

Audits current source truth instead of silently substituting a 50-trade
standard. Historical v1.2 disclosures remain immutable; current social-post
waiver remains mandatory. None of this constitutes legal release.
"""
from __future__ import annotations
from dataclasses import dataclass

from .order_readiness import PREPURCHASE_DISCLOSURES, TERMS_VERSION
from .plan1_buyer_disclosure_v12 import buyer_disclosure
from .plan1_buyer_no_social_amendment import (
    buyer_no_social_post_amendment, current_plan1_buyer_copy,
)
from .rules import POLICY
from .xauusd_v13_preflight import DRAFT_CONTRACT_VERSION


@dataclass(frozen=True)
class GoldTermsGate:
    current_contract_version: str
    proposed_contract_version: str
    blockers: tuple[str, ...]
    approved_bilingual_terms_signed: bool = False
    contract_version_propagated_to_intake: bool = False
    public_checkout_allowed: bool = False
    invoice_allowed: bool = False
    customer_enrollment_allowed: bool = False
    live_trading_allowed: bool = False
    legal_review_complete: bool = False
    independently_verified_capital: bool = False
    independently_verified_broker_account: bool = False


def audit_v13_gold_terms() -> GoldTermsGate:
    blockers = ["v13_signed_customer_terms_absent",
                "v13_contract_intake_provenance_not_integrated",
                "v13_independent_legal_release_unverified",
                "v13_capital_and_broker_release_unverified"]
    try:
        historical = buyer_disclosure()
        current = current_plan1_buyer_copy()
        waiver = buyer_no_social_post_amendment()
        if (historical.contract_version != TERMS_VERSION
                or TERMS_VERSION != "2026-11-15/v1.2"
                or POLICY.version != TERMS_VERSION):
            blockers.append("historic_contract_source_version_drift")
        old_combined = (
            "50 distinct, reconciled CLOSED positions in total across both"
            in historical.en
        )
        current_each = any(
            "50 independently verified closed positions in EACH" in statement
            for statement in PREPURCHASE_DISCLOSURES
        )
        if old_combined and current_each:
            blockers.append("fifty_trades_per_phase_vs_combined_conflict")
        elif not old_combined or not current_each:
            blockers.append("fifty_trade_source_text_changed_requires_review")
        if (current.instagram_posts_required != 0
                or current.facebook_posts_required != 0
                or current.requires_separate_buyer_contract_acceptance is not True
                or current.payment_enabled is not False
                or current.enrollment_enabled is not False):
            blockers.append("no_social_post_waiver_or_no_payment_drift")
        if (waiver.en not in current.en
                or waiver.fa not in current.fa
                or waiver.instagram_posts_required != 0
                or waiver.facebook_posts_required != 0
                or waiver.posting_a_condition_of_challenge_pass is not False
                or waiver.posting_a_condition_of_funded_profit is not False):
            blockers.append("no_social_waiver_language_unreviewed")
    except (ValueError, RuntimeError, AttributeError) as exc:
        blockers.append("buyer_disclosure_source_failed_closed")
    return GoldTermsGate(
        current_contract_version=TERMS_VERSION,
        proposed_contract_version=DRAFT_CONTRACT_VERSION,
        blockers=tuple(dict.fromkeys(blockers)),
    )

"""Canonical MOJ PROP release gate.

This module joins the policy-integrity, challenge-review and sector-review
contracts into one auditable decision. It never creates invoices, activates
checkout, places broker orders, moves funds or authorizes deployment.

An owner declaration (including Plan 1 being called funded) is kept separate
from independently reconciled capital and broker evidence.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.commercialization_readiness import assess_sector
from .challenge_commerce import assess_challenge_checkout
from .plans import DEFAULT_PLAN_CODE, plan_for_code
from .policy_integrity import policy_drift_defects


@dataclass(frozen=True)
class MojPropReleaseDecision:
    """A fail-closed review result, never an activation command."""

    plan_code: str
    outcome: str
    eligible_for_commercial_review: bool
    policy_consistent: bool
    challenge_reviewable: bool
    sector_reviewable: bool
    sector_evidence_percent: int
    blockers: tuple[str, ...]
    owner_declared_active: bool
    owner_declared_funded: bool
    independent_capital_proof_on_record: bool
    independent_broker_proof_on_record: bool
    checkout_enabled: bool = False
    invoice_created: bool = False
    trading_enabled: bool = False
    release_authorized: bool = False


def _add_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def assess_moj_prop_release(
    *,
    merchant_tenant,
    free_treasury_usd,
    protected_reserves_usd,
    existing_commitments_usd=0,
    required_first_tier_accounts=1,
    challenge_attestations=None,
    sector_attestations=None,
    plan_code=DEFAULT_PLAN_CODE,
) -> MojPropReleaseDecision:
    """Evaluate one canonical plan without producing a live commercial side effect.

    "challenge_attestations" and "sector_attestations" are evidence inputs;
    literal True is required by the delegated gates. The plan registry's
    independent-proof fields are also required, so a caller cannot convert an
    owner declaration or a numeric balance into independent proof.
    """

    plan = plan_for_code(plan_code)
    defects = policy_drift_defects()
    offer = assess_challenge_checkout(
        merchant_tenant=merchant_tenant,
        free_treasury_usd=free_treasury_usd,
        protected_reserves_usd=protected_reserves_usd,
        existing_commitments_usd=existing_commitments_usd,
        required_first_tier_accounts=required_first_tier_accounts,
        attestations=challenge_attestations,
        plan_code=plan.code,
    )
    sector = assess_sector("moj_prop", sector_attestations)

    blockers: list[str] = []
    for defect in defects:
        _add_unique(blockers, f"canonical_policy:{defect}")
    for blocker in offer.blockers:
        _add_unique(blockers, f"challenge:{blocker}")
    for missing in sector.missing:
        _add_unique(blockers, f"sector:{missing}")

    if not plan.business_active_owner_declared:
        _add_unique(blockers, "plan_not_owner_active")
    if plan.temporary_owner_hold:
        _add_unique(blockers, "plan_temporarily_inactive_pending_owner_funding")
    if not plan.funding_independently_verified:
        _add_unique(blockers, "independent_capital_proof_required")
    if not plan.broker_live_account_independently_verified:
        _add_unique(blockers, "independent_broker_proof_required")

    policy_consistent = not defects
    challenge_reviewable = offer.eligible_for_external_legal_review
    sector_reviewable = sector.outcome == "eligible_for_commercial_review"
    eligible = not blockers
    return MojPropReleaseDecision(
        plan_code=plan.code,
        outcome="reviewable_not_authorized" if eligible else "not_released",
        eligible_for_commercial_review=eligible,
        policy_consistent=policy_consistent,
        challenge_reviewable=challenge_reviewable,
        sector_reviewable=sector_reviewable,
        sector_evidence_percent=sector.percent_evidenced,
        blockers=tuple(blockers),
        owner_declared_active=plan.business_active_owner_declared,
        owner_declared_funded=plan.capital_funded_owner_declared,
        independent_capital_proof_on_record=plan.funding_independently_verified,
        independent_broker_proof_on_record=plan.broker_live_account_independently_verified,
    )

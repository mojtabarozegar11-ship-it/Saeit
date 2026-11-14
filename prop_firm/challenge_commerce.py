"""Nonpayment contract for the first-priority 30 TRX Moj Prop challenge.

A signed tenant context alone cannot authorize selling an assessment promising
real capital. Only independently evidenced legal, broker, treasury, identity,
customer contract and settlement controls can make a proposal reviewable.
This is an offline arithmetic readiness gate, NOT a checkout implementation.
"""
from dataclasses import dataclass
from decimal import Decimal

from core.tron_tenant_policy import TenantDecision
from .economics import funded_capacity
from .rules import POLICY, LEVELS

REQUIRED = (
    "jurisdiction_authorized",
    "terms_approved_and_translated",
    "real_funding_broker_contract_verified",
    "minimum_order_size_compatible_with_100_usd",
    "identity_screening_ready",
    "independently_reconciled_tron_invoice_ready",
    "challenge_simulation_clearly_disclosed",
    "future_tier_financing_independently_documented",
    "dispute_and_refund_process_ready",
)


@dataclass(frozen=True)
class ChallengeOfferDecision:
    fee_trx: Decimal
    first_real_tier_usd: Decimal
    final_tier_usd: Decimal
    audited_cash_free_usd: Decimal
    maximum_initial_funded_accounts: int
    capital_shortfall_usd: Decimal
    eligible_for_external_legal_review: bool
    blockers: tuple[str, ...]
    checkout_enabled: bool = False
    invoice_created: bool = False
    trading_enabled: bool = False


def assess_challenge_checkout(*, merchant_tenant, free_treasury_usd,
                              protected_reserves_usd, existing_commitments_usd=0,
                              required_first_tier_accounts=1, attestations=None):
    if not isinstance(merchant_tenant, TenantDecision):
        raise ValueError("Trusted merchant scope needed")
    if (type(required_first_tier_accounts) is not int
            or not 1 <= required_first_tier_accounts <= 10000):
        raise ValueError("At least one bounded real account must be backed")

    if attestations is None:
        attestations = {}
    if not isinstance(attestations, dict):
        raise ValueError("Malformed readiness attestations")
    blockers = [
        key for key in REQUIRED if attestations.get(key) is not True
    ]
    if (merchant_tenant.host not in ("mojplaywin.com", "www.mojplaywin.com")
            or merchant_tenant.brand != "moj_prop"
            or merchant_tenant.eligible_for_checkout_review is not True
            or merchant_tenant.payment_enabled is not False
            or merchant_tenant.invoice_created is not False):
        blockers.append("dedicated_moj_prop_tron_merchant_not_verified")
    capacity = funded_capacity(
        tier_index=0, unencumbered_cash_usd=free_treasury_usd,
        protected_reserve_usd=protected_reserves_usd,
        already_committed_usd=existing_commitments_usd,
        requested_new_accounts=required_first_tier_accounts,
    )
    if capacity.maximum_fully_funded_accounts < required_first_tier_accounts:
        blockers.append("real_initial_account_capital_shortfall")
    return ChallengeOfferDecision(
        fee_trx=POLICY.entry_trx,
        first_real_tier_usd=LEVELS[0],
        final_tier_usd=LEVELS[-1],
        audited_cash_free_usd=capacity.net_allocable_usd,
        maximum_initial_funded_accounts=capacity.maximum_fully_funded_accounts,
        capital_shortfall_usd=capacity.additional_needed_usd,
        eligible_for_external_legal_review=not blockers,
        blockers=tuple(blockers),
        checkout_enabled=False,
        invoice_created=False,
        trading_enabled=False,
    )

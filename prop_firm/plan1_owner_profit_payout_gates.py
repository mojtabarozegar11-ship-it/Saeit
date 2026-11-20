"""Cycle B: legal/accounting proof requirements for owner-held account payout.

This B source module owns only buyer-terms and accounting-readiness policy.
It never approves, initiates, signs, publishes or settles a crypto payment;
the independently audited treasury/payment cycle must own those actions.
"""
from dataclasses import dataclass

REQUIRED_PROFIT_PAYOUT_PROOFS = (
    "buyer_passed_both_demo_phases",
    "broker_third_party_trading_permission_in_force",
    "source_real_account_owner_custody_verified",
    "buyer_specific_closed_trade_attribution_verified",
    "complete_realized_profit_broker_statement_reconciled",
    "broker_trading_fees_and_swap_reconciled",
    "unrealized_pnl_excluded",
    "negative_prior_period_loss_carryforward_reconciled",
    "no_prior_payment_of_same_period_or_positions",
    "settlement_period_and_profit_70_30_signed_by_buyer",
    "company_broker_withdrawal_obeys_original_source_rules",
    "company_treasury_funds_independently_available",
    "payout_legality_and_beneficiary_kyc_sanctions_verified",
    "beneficiary_wallet_ownership_and_network_verified",
    "payout_token_fx_quote_and_conversion_costs_disclosed",
    "actual_transfer_network_fee_pre_disclosed_and_verified",
    "refund_dispute_and_support_process_accessible",
    "independent_dual_approval_and_audit_ledger_ready",
)

@dataclass(frozen=True)
class PrivateProfitPayoutEvidenceReview:
    eligible_for_independent_payout_finance_review: bool
    missing: tuple[str, ...]
    stage: str = "PAYOUT_FINANCE_REVIEW_ONLY"
    owner_account_verified_by_this_module: bool = False
    broker_delegation_authorized_by_this_module: bool = False
    beneficiary_identity_verified_by_this_module: bool = False
    broker_withdrawal_authorized: bool = False
    crypto_transfer_authorized: bool = False
    transfer_fee_paid: bool = False
    transfer_broadcast: bool = False
    transaction_confirmed: bool = False
    trader_profit_liability_created: bool = False

def review_private_profit_payout_proofs(*, evidence):
    """Pure exact-key fail closed; never trust buyer flags as real documents.

    Every source input requires separately authenticated independent authority
    and immutable reconciliation; even ALL True is only a review candidate.
    """
    if type(evidence) is not dict or set(evidence) != set(REQUIRED_PROFIT_PAYOUT_PROOFS):
        raise ValueError("complete independent profit-payout proof set required")
    missing=tuple(k for k in REQUIRED_PROFIT_PAYOUT_PROOFS if evidence[k] is not True)
    return PrivateProfitPayoutEvidenceReview(
        eligible_for_independent_payout_finance_review=not missing,
        missing=missing,
    )

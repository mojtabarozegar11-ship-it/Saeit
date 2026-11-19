"""Plan 1 source-only DEMO -> REAL account boundary, never an account issuer.

The buyer can begin both evaluation phases on simulated accounts, WITHOUT a
real brokerage account. A separately reviewed and genuinely funded REAL broker
account can be considered only AFTER both simulations are independently passed.

NOT a substitute for merchant legal sale requirements or any applicable
pre-purchase eligibility / AML / sanctions checks. KYC of the REAL broker
account is deferred to the real-account stage whenever law permits.
"""
from dataclasses import dataclass
from .order_readiness import SKU, TERMS_VERSION

DEMO_STAGES = ("phase_one", "phase_two")
REAL_STAGE = "funded"
REQUIRED_REAL_ACCOUNT_PROOFS = (
    "stage_one_independently_passed",
    "stage_two_independently_passed",
    "combined_fifty_closed_positions_verified",
    "six_days_in_each_stage_verified",
    "twenty_eight_day_window_respected",
    "risk_limits_independently_verified",
    "real_buyer_identity_matches_challenge",
    "buyer_age_and_country_legally_eligible",
    "broker_kyc_fully_verified",
    "signed_real_funded_account_agreement",
    "real_100_usd_unencumbered_capital_verified",
    "authorized_live_broker_account_verified",
    "independent_merchant_and_funding_authorization",
    "settled_challenge_purchase_ledger_verified",
)


@dataclass(frozen=True)
class Plan1PhaseAccountBoundary:
    sku: str = SKU
    contract_version: str = TERMS_VERSION
    phase_one_kind: str = "phase_one"
    phase_two_kind: str = "phase_two"
    phase_one_simulated: bool = True
    phase_two_simulated: bool = True
    real_account_required_to_start_phase_one: bool = False
    real_account_required_to_start_phase_two: bool = False
    broker_live_kyc_required_to_start_demo: bool = False
    legal_buyer_checks_may_apply_to_challenge_purchase: bool = True
    real_broker_account_only_after_two_verified_passes: bool = True
    no_instant_real_funding_promised: bool = True
    # Owner-reported existing verified LiteFinance account. Broker's explicit
    # authorization for delegated order routing remains a separate proof.
    owner_existing_litefinance_account_declared: bool = True
    existing_owner_account_broker_verified_by_this_code: bool = False
    delegated_customer_trading_authorized_by_this_code: bool = False
    buyer_specific_broker_account_opening_required: bool = False
    buyer_receives_real_trading_principal: bool = False
    buyer_receives_owner_password_or_2fa: bool = False
    buyer_can_withdraw_from_broker: bool = False
    buyer_receives_broker_direct_crypto_payout: bool = False
    crypto_profit_payment_from_separate_treasury_only: bool = True
    real_account_created: bool = False
    invoice_created: bool = False
    payment_processed: bool = False
    real_broker_kyc_completed: bool = False


@dataclass(frozen=True)
class FundedTransitionReview:
    sku: str
    contract_version: str
    eligible_for_separate_real_account_review: bool
    missing: tuple[str, ...]
    status: str
    verified_real_account_created: bool = False
    broker_account_opened_by_this_module: bool = False
    real_capital_transferred_by_this_module: bool = False
    live_order_authorized: bool = False
    challenge_invoice_created: bool = False
    marketing_permission_created: bool = False


def phase_account_boundary(*, sku=SKU, terms_version=TERMS_VERSION):
    """Describe demo-only phases without creating a customer or account."""
    if type(sku) is not str or sku != SKU:
        raise ValueError("Only the real MOJ-PROP-01 challenge is supported")
    if type(terms_version) is not str or terms_version != TERMS_VERSION:
        raise ValueError("Historical contract and explicit amendment must be reviewed")
    return Plan1PhaseAccountBoundary()


def review_demo_to_real_transition(
    *, independently_verified: dict, sku=SKU, terms_version=TERMS_VERSION,
):
    """Require actual external evidence for each REAL-account prerequisite.

    Inputs MUST be set by trusted independent reviewers, not a buyer's form,
    demo results alone, a broker URL, or a signed but unverified JSON object.
    Here "broker_kyc_fully_verified" is evidence of identity verification
    for the ACTUAL lawful holder of the existing LiteFinance account, NOT
    a requirement to open a new customer-owned brokerage account. All other
    bidder/beneficiary eligibility and sanctions checks still apply.
    Even all True authorizes a review ONLY, never opens the account.
    """
    phase_account_boundary(sku=sku, terms_version=terms_version)
    if type(independently_verified) is not dict:
        raise TypeError("Independent named evidence is required")
    if set(independently_verified) != set(REQUIRED_REAL_ACCOUNT_PROOFS):
        raise ValueError("Missing or extra real-account evidence fields")
    missing = tuple(
        gate for gate in REQUIRED_REAL_ACCOUNT_PROOFS
        if independently_verified[gate] is not True
    )
    return FundedTransitionReview(
        sku=SKU, contract_version=TERMS_VERSION,
        eligible_for_separate_real_account_review=not missing,
        missing=missing,
        status=("READY_FOR_SEPARATE_BROKER_APPROVAL_REVIEW_ONLY"
                if not missing else "REAL_ACCOUNT_BLOCKED_PENDING_EVIDENCE"),
    )

"""MOJ PROP real-funded Plan 1: customer entitlement vs merchant delivery risk.

Pure, source-only contractual projection: never creates a paid order, cash
transfer, funded broker account, enrollment, new contract, invoice or trading
permission. A company liquidity shortfall is NOT a trader rule violation.
Merchant-provided wallet-balance statements are declarations, never proof.

The date supplied here must come from the buyer's signed/versioned contract;
this module does not invent a delivery SLA or retroactively amend contracts.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .plans import plan_for_code
from .rules import LEVELS

PLAN_CODE = "MOJ-PROP-01"


@dataclass(frozen=True)
class FundingObligationReview:
    plan_code: str
    tier_capital_usd: Decimal
    final_tier_usd: Decimal
    tier_index: int
    status: str
    customer_conditions_verified: bool
    company_delivery_obligation: bool
    company_delivery_overdue: bool
    trader_failed_due_to_company_funding: bool = False
    delivery_independently_proven: bool = False
    funded_account_auto_expires_after_challenge: bool = False
    checkout_authorized: bool = False
    capital_transfer_authorized: bool = False
    reasons: tuple[str, ...] = ()


def _boolean(value, label):
    if type(value) is not bool:
        raise ValueError(f"{label} must be trusted boolean evidence")
    return value


def _utc(value, label):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be an aware timestamp from a trusted source")
    return value.astimezone(timezone.utc)


def _amount(value):
    if isinstance(value, (bool, float)) or type(value) not in (str, int, Decimal):
        raise ValueError("exact assigned USD amount required")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError("invalid funded account USD balance") from None
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("non-finite or negative assigned capital")
    return parsed


def assess_funded_delivery(
    *, plan_code: str, tier_index: int,
    challenge_pass_verified: bool, promotion_verified: bool,
    trading_rules_compliant: bool, kyc_verified: bool,
    signed_customer_contract_verified: bool,
    independent_broker_account_verified: bool,
    independent_funding_allocation_verified: bool,
    assigned_capital_usd,
    contractual_delivery_due_at: datetime | None,
    now: datetime,
) -> FundingObligationReview:
    """Separate customer achievement from company capacity and duty.

    Every verification boolean must be supplied by an independent trusted
    server-side adapter, not a public request or the owner's assertion.
    Promotion verification is required ABOVE the plan's starting tier.
    Contractual due date must come from a signed contract and verified
    milestone event; a missing deadline is explicitly a merchant gap.
    """
    if type(plan_code) is not str or plan_code != PLAN_CODE:
        raise ValueError("only canonical real funded Plan 1 is in scope")
    plan = plan_for_code(plan_code)
    if plan.temporary_owner_hold or not plan.business_active_owner_declared:
        raise ValueError("Plan 1 is not owner-declared active")
    if (type(tier_index) is not int or
            not plan.starting_tier_index <= tier_index < len(LEVELS)):
        raise ValueError("unsupported or below-contract funding tier")
    flags = {
        "challenge_pass_verified": challenge_pass_verified,
        "promotion_verified": promotion_verified,
        "trading_rules_compliant": trading_rules_compliant,
        "kyc_verified": kyc_verified,
        "signed_customer_contract_verified": signed_customer_contract_verified,
        "independent_broker_account_verified": independent_broker_account_verified,
        "independent_funding_allocation_verified": independent_funding_allocation_verified,
    }
    for label, flag in flags.items():
        _boolean(flag, label)
    capital = _amount(assigned_capital_usd)
    current_time = _utc(now, "now")
    if contractual_delivery_due_at is not None:
        due = _utc(contractual_delivery_due_at, "contractual delivery due")
    else:
        due = None

    required_conditions = [
        ("signed_customer_contract_missing", signed_customer_contract_verified),
        ("challenge_pass_not_independently_verified", challenge_pass_verified),
        ("trading_compliance_not_verified", trading_rules_compliant),
        ("customer_kyc_not_verified", kyc_verified),
    ]
    if tier_index > plan.starting_tier_index:
        required_conditions.append(
            ("promotion_milestone_not_verified", promotion_verified)
        )
    missing = tuple(key for key, flag in required_conditions if not flag)
    customer_verified = not missing
    independently_delivered = (
        customer_verified and independent_broker_account_verified
        and independent_funding_allocation_verified
        and capital >= LEVELS[tier_index]
    )
    # Seller's missing funding must never mark a qualified trader as failed.
    if not customer_verified:
        status = "awaiting_customer_qualification_evidence"
        reasons = missing
    elif independently_delivered:
        status = "funding_delivered_with_independent_evidence"
        reasons = ()
    elif due is None:
        status = "company_contract_delivery_deadline_missing"
        reasons = ("merchant_must_define_contractual_delivery_deadline",)
    elif current_time > due:
        status = "company_funding_delivery_overdue"
        reasons = ("merchant_must_fulfill_or_apply_customer_remedy",)
    else:
        status = "company_funding_delivery_pending"
        reasons = ("merchant_funding_or_broker_evidence_pending",)
    return FundingObligationReview(
        plan_code=PLAN_CODE,
        tier_capital_usd=LEVELS[tier_index],
        final_tier_usd=LEVELS[-1],
        tier_index=tier_index,
        status=status,
        customer_conditions_verified=customer_verified,
        company_delivery_obligation=customer_verified,
        company_delivery_overdue=status == "company_funding_delivery_overdue",
        delivery_independently_proven=independently_delivered,
        reasons=reasons,
    )

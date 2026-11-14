"""Moj Prop capital-allocation and cohort economics — projections only.

All prices and conversion rates are explicit user assumptions, never live FX quotes.
No checkout, account activation, transfers, trading, or revenue recording.
Company-paid losses and payout liabilities stay on the company's balance sheet.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from .rules import LEVELS, POLICY, dec
from .plans import DEFAULT_PLAN_CODE, plan_for_code


def nonnegative(value, field):
    result = dec(value)
    if result < 0:
        raise ValueError(f"{field} cannot be negative")
    return result


def valid_count(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def proportion(value, field):
    result = nonnegative(value, field)
    if result > 100:
        raise ValueError(f"{field} must not exceed 100%")
    return result


def capital_level(tier_index):
    if isinstance(tier_index, bool) or not isinstance(tier_index, int):
        raise ValueError("tier_index must be an integer")
    if tier_index < 0 or tier_index >= len(LEVELS):
        raise ValueError("tier_index out of range")
    return LEVELS[tier_index]


@dataclass(frozen=True)
class CapacityEstimate:
    level_usd: Decimal
    unencumbered_usd: Decimal
    protected_reserve_usd: Decimal
    operating_buffer_usd: Decimal
    net_allocable_usd: Decimal
    maximum_fully_funded_accounts: int
    additional_needed_usd: Decimal


def funded_capacity(*, tier_index, unencumbered_cash_usd,
                    protected_reserve_usd, operating_buffer_usd=0,
                    already_committed_usd=0, requested_new_accounts=1):
    """Always subtract reserve, costs and existing obligations before allocating.

    This is an arithmetic gate, not proof of actual custody or legal authority.
    """
    tier = capital_level(tier_index)
    cash = nonnegative(unencumbered_cash_usd, "unencumbered_cash_usd")
    reserve = nonnegative(protected_reserve_usd, "protected_reserve_usd")
    operations = nonnegative(operating_buffer_usd, "operating_buffer_usd")
    commitments = nonnegative(already_committed_usd, "already_committed_usd")
    requested = valid_count(requested_new_accounts, "requested_new_accounts")
    available = max(Decimal("0"), cash - reserve - operations - commitments)
    count = int((available / tier).to_integral_value(rounding=ROUND_FLOOR))
    shortfall = max(Decimal("0"), tier * requested - available)
    return CapacityEstimate(tier, cash, reserve, operations, available,
                            count, shortfall)


@dataclass(frozen=True)
class CohortEstimate:
    applicants: int
    hypothetical_pass_count: int
    trx_fees_total: Decimal
    gross_fee_usd: Decimal
    acquisition_cost_usd: Decimal
    payment_cost_usd: Decimal
    support_cost_usd: Decimal
    overhead_usd: Decimal
    fee_contribution_usd: Decimal
    first_tier_escrow_requirement_usd: Decimal
    ultimate_tier_capital_usd: Decimal
    gross_revenue_not_actual: bool = True
    plan_code: str = DEFAULT_PLAN_CODE


def estimate_cohort(*, applicants, trx_usd_assumption, pass_rate_percent,
                    plan_code=DEFAULT_PLAN_CODE,
                    acquisition_cost_per_applicant_usd=0,
                    payment_cost_per_applicant_usd=0,
                    support_cost_per_applicant_usd=0,
                    allocated_overhead_usd=0):
    """Projected cohort counts round UP to avoid understating funding needs."""
    plan = plan_for_code(plan_code)
    count = valid_count(applicants, "applicants")
    rate = nonnegative(trx_usd_assumption, "trx_usd_assumption")
    if rate == 0:
        raise ValueError("trx_usd_assumption must be positive")
    pass_rate = proportion(pass_rate_percent, "pass_rate_percent")
    acquire = nonnegative(acquisition_cost_per_applicant_usd, "acquisition_cost_per_applicant_usd")
    pay = nonnegative(payment_cost_per_applicant_usd, "payment_cost_per_applicant_usd")
    support = nonnegative(support_cost_per_applicant_usd, "support_cost_per_applicant_usd")
    overhead = nonnegative(allocated_overhead_usd, "allocated_overhead_usd")

    passed = int((Decimal(count) * pass_rate / 100).to_integral_value(rounding=ROUND_CEILING))
    fees_trx = plan.entry_fee_trx * count
    gross = fees_trx * rate
    acquisition = acquire * count
    payment = pay * count
    support_total = support * count
    return CohortEstimate(
        applicants=count,
        hypothetical_pass_count=passed,
        trx_fees_total=fees_trx,
        gross_fee_usd=gross,
        acquisition_cost_usd=acquisition,
        payment_cost_usd=payment,
        support_cost_usd=support_total,
        overhead_usd=overhead,
        fee_contribution_usd=gross - acquisition - payment - support_total - overhead,
        first_tier_escrow_requirement_usd=plan.starting_capital_usd * passed,
        ultimate_tier_capital_usd=plan.maximum_capital_usd * passed,
        plan_code=plan.code,
    )


def trading_breakeven_win_rate(*, win_percent, loss_percent,
                               company_share_percent=POLICY.company_profit_share_pct):
    """Hypothetical fraction of equal-size independent profitable periods needed.

    Wins earn only the company share; full losses are borne by the company.
    Excludes spread, liquidity costs, tail risks, and customer operating costs.
    """
    win = nonnegative(win_percent, "win_percent")
    loss = nonnegative(loss_percent, "loss_percent")
    share = proportion(company_share_percent, "company_share_percent")
    company_positive = win * share / Decimal("100")
    if company_positive == 0 and loss == 0:
        raise ValueError("No positive or negative trading outcome")
    if company_positive == 0:
        return Decimal("100")
    return loss * Decimal("100") / (loss + company_positive)


def total_parallel_tier_commitment():
    """One fully backed account in each of fourteen tiers."""
    return sum(LEVELS, Decimal("0"))


def conservative_realization_gate(*, treasury_verified, legal_approved,
                                  broker_approved, kyc_approved,
                                  customer_contract_approved, available_cash_usd,
                                  tier_index, payout_reserve_usd,
                                  already_committed_usd=0):
    """Confirm prerequisites before even *recommending* a real-account allocation.

    This calculator never authorizes live execution or guarantees the funding.
    """
    capacity = funded_capacity(
        tier_index=tier_index,
        unencumbered_cash_usd=available_cash_usd,
        protected_reserve_usd=payout_reserve_usd,
        already_committed_usd=already_committed_usd,
    )
    checks = {
        "treasury_verified": treasury_verified is True,
        "legal_approved": legal_approved is True,
        "broker_approved": broker_approved is True,
        "kyc_approved": kyc_approved is True,
        "customer_contract_approved": customer_contract_approved is True,
        "cash_available": capacity.maximum_fully_funded_accounts >= 1,
    }
    return {
        "eligible_for_human_review": all(checks.values()),
        "checks": checks,
        "shortfall_usd": capacity.additional_needed_usd,
        "live_trading_enabled": False,
        "payment_collection_enabled": False,
    }

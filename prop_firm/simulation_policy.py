"""Canonical owner-directed simulation model for MOJ PROP.

Both the evaluation and post-pass funded stage are simulated. Virtual
principal is never withdrawable. Performance rewards are real company
obligations and require an independently verified reserve before admissions.
This module is arithmetic/policy only: it never charges, trades, transfers or
authorizes a payout.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

D = Decimal


@dataclass(frozen=True)
class SimulationPolicy:
    contract_version: str = "2026-11-19/simulation-v1"
    account_mode: str = "simulated"
    payout_mode: str = "real_performance_reward"
    starting_balance_usd: Decimal = D("1000")
    challenge_window_days: int = 60
    daily_loss_limit_pct: Decimal = D("6")
    total_loss_limit_pct: Decimal = D("8")
    max_risk_per_trade_pct: Decimal = D("3")
    max_open_risk_pct: Decimal = D("4")
    canonical_best_day_share_pct: Decimal = D("32")
    proposed_best_day_share_pct: Decimal = D("50")
    entry_fee_trx: Decimal = D("30")
    retry_fee_trx: Decimal = D("18")
    retry_discount_pct: Decimal = D("40")
    minimum_closed_positions: int = 50
    post_visibility_days: int = 28
    virtual_principal_withdrawable: bool = False
    customer_deposit_required: bool = False
    real_orders_enabled: bool = False


SIMULATION_POLICY = SimulationPolicy()


@dataclass(frozen=True)
class RewardReserveEstimate:
    applicants: int
    pass_count: int
    reward_claimants: int
    challenge_revenue_trx: Decimal
    reward_reserve_usd: Decimal
    retry_revenue_trx: Decimal
    total_revenue_trx: Decimal
    assumptions_are_projections: bool = True


def _rate(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an exact nonnegative rate")
    result = D(str(value))
    if not result.is_finite() or result < 0 or result > 100:
        raise ValueError(f"{name} must be between 0 and 100")
    return result


def _count(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def estimate_reward_reserve(
    *,
    applicants,
    pass_rate_pct,
    reward_claim_rate_pct,
    average_reward_usd,
    retry_applicants=0,
    retry_fee_trx=None,
):
    """Stress reserve for real performance rewards, not virtual principal.

    The function rounds claimant counts upward so a reserve cannot be
    understated by fractional cohorts. It is not proof of cash custody.
    """
    count = _count(applicants, "applicants")
    retries = _count(retry_applicants, "retry_applicants")
    pass_rate = _rate(pass_rate_pct, "pass_rate_pct")
    claim_rate = _rate(reward_claim_rate_pct, "reward_claim_rate_pct")
    reward = D(str(average_reward_usd))
    if not reward.is_finite() or reward < 0:
        raise ValueError("average_reward_usd must be a finite nonnegative amount")
    retry_fee = (
        SIMULATION_POLICY.retry_fee_trx
        if retry_fee_trx is None else D(str(retry_fee_trx))
    )
    if not retry_fee.is_finite() or retry_fee < 0:
        raise ValueError("retry_fee_trx must be finite and nonnegative")
    passed = int((D(count) * pass_rate / D("100")).to_integral_value(
        rounding=ROUND_CEILING
    ))
    claimants = int((D(passed) * claim_rate / D("100")).to_integral_value(
        rounding=ROUND_CEILING
    ))
    challenge_revenue = D(count) * SIMULATION_POLICY.entry_fee_trx
    retry_revenue = D(retries) * retry_fee
    reserve = D(claimants) * reward
    return RewardReserveEstimate(
        applicants=count,
        pass_count=passed,
        reward_claimants=claimants,
        challenge_revenue_trx=challenge_revenue,
        reward_reserve_usd=reserve,
        retry_revenue_trx=retry_revenue,
        total_revenue_trx=challenge_revenue + retry_revenue,
    )

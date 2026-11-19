"""Deterministic prop-firm v1.2 policy engine. No external financial side effects.

Never trust request/browser input as evidence for funding, progression or payout.
Amounts use Decimal; source verification and atomic persistence live OUTSIDE this module.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from .simulation_policy import SIMULATION_POLICY

D = Decimal
CENT = D("0.01")
LEVELS = tuple(map(D, (
    "1000", "1500", "2000", "3000", "5000", "7500", "10000", "15000",
    "20000", "35000", "50000", "70000", "85000", "100000",
)))

def dec(value):
    """Explicitly reject imprecise floats, bools and non-finite inputs."""
    if isinstance(value, (bool, float)):
        raise ValueError("Use exact Decimal or decimal string, not float/bool")
    try:
        result = D(str(value))
    except (ValueError, ArithmeticError) as exc:
        raise ValueError("Invalid decimal") from exc
    if not result.is_finite():
        raise ValueError("Non-finite decimal")
    return result

def percent(amount, rate):
    return dec(amount) * dec(rate) / D("100")

@dataclass(frozen=True)
class Policy:
    version: str = SIMULATION_POLICY.contract_version
    canonical_bot: str = "mojtaba.bot.ai"
    entry_trx: Decimal = SIMULATION_POLICY.entry_fee_trx
    retry_trx: Decimal = SIMULATION_POLICY.retry_fee_trx
    retry_discount_pct: Decimal = SIMULATION_POLICY.retry_discount_pct
    phase_one_goal_pct: Decimal = D("9.6")
    phase_two_goal_pct: Decimal = D("6")
    min_challenge_days: int = 6
    min_closed_trades_per_challenge: int = SIMULATION_POLICY.minimum_closed_positions
    trader_bots_allowed: bool = True
    social_posts_per_platform_per_challenge: int = 1
    social_posting_platforms: tuple[str, str] = ("instagram", "facebook")
    max_daily_loss_pct: Decimal = SIMULATION_POLICY.daily_loss_limit_pct
    max_total_loss_pct: Decimal = SIMULATION_POLICY.total_loss_limit_pct
    best_day_share_pct: Decimal = SIMULATION_POLICY.canonical_best_day_share_pct
    proposed_best_day_share_pct: Decimal = SIMULATION_POLICY.proposed_best_day_share_pct
    order_risk_pct: Decimal = SIMULATION_POLICY.max_risk_per_trade_pct
    aggregate_risk_pct: Decimal = SIMULATION_POLICY.max_open_risk_pct
    promotion_goal_pct: Decimal = D("3.6")
    promotion_min_days: int = 12
    promotion_cycle_days: int = 30
    trader_profit_share_pct: Decimal = D("70")
    company_profit_share_pct: Decimal = D("30")
    inactivity_notice_days: int = 14
    inactivity_grace_days: int = 14
    completion_deadline_days: int = SIMULATION_POLICY.challenge_window_days
    challenge_window_days: int = SIMULATION_POLICY.challenge_window_days
    post_visibility_days: int = SIMULATION_POLICY.post_visibility_days
    account_mode: str = SIMULATION_POLICY.account_mode
    payout_mode: str = SIMULATION_POLICY.payout_mode
    virtual_principal_withdrawable: bool = SIMULATION_POLICY.virtual_principal_withdrawable
    customer_deposit_required: bool = SIMULATION_POLICY.customer_deposit_required
    real_orders_enabled: bool = SIMULATION_POLICY.real_orders_enabled
    trx_checkout_enabled: bool = False

POLICY = Policy()

@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[str, ...]
    daily_equity_floor: Decimal
    total_equity_floor: Decimal

@dataclass(frozen=True)
class ChallengeDecision:
    passed: bool
    reasons: tuple[str, ...]
    goal_usd: Decimal
    verified_profit_usd: Decimal

@dataclass(frozen=True)
class PromotionDecision:
    eligible: bool
    reasons: tuple[str, ...]
    current_level: Decimal
    next_level: Decimal

@dataclass(frozen=True)
class FundingDecision:
    authorized: bool
    reasons: tuple[str, ...]
    required_cash_usd: Decimal

@dataclass(frozen=True)
class Payout:
    eligible_profit_usd: Decimal
    trader_usd: Decimal
    company_usd: Decimal
    new_allocated_high_water_usd: Decimal

def _positive(value, name):
    n = dec(value)
    if n <= 0:
        raise ValueError(f"{name} must be positive")
    return n

def _nonnegative(value, name):
    n = dec(value)
    if n < 0:
        raise ValueError(f"{name} must be nonnegative")
    return n

def _days(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be nonnegative integer")
    return value

def assess_risk(*, account_capital, equity, day_open_equity):
    """Floors use original tier capital and authoritative UTC day-opening equity.

    Breaches include floating P&L and trigger at-or-below either floor.
    """
    capital = _positive(account_capital, "account_capital")
    current = _nonnegative(equity, "equity")
    day_open = _nonnegative(day_open_equity, "day_open_equity")
    daily_floor = day_open - percent(capital, POLICY.max_daily_loss_pct)
    total_floor = capital - percent(capital, POLICY.max_total_loss_pct)
    reasons = []
    if current <= daily_floor:
        reasons.append("daily_loss_floor_reached")
    if current <= total_floor:
        reasons.append("total_loss_floor_reached")
    return RiskDecision(not reasons, tuple(reasons), daily_floor, total_floor)

def _consistency_reasons(*, verified_profit, max_profitable_day):
    maximum = _nonnegative(max_profitable_day, "max_profitable_day")
    if verified_profit <= 0 or maximum > percent(verified_profit, POLICY.best_day_share_pct):
        return ("profit_consistency_not_met",)
    return ()

def assess_challenge(*, phase, account_capital, realized_net_profit,
                     trading_days, max_profitable_day, risk, evidence_verified=False,
                     prior_phase_passed=False, social_posts_verified=False,
                     contract_version=None, verified_cumulative_trades=0):
    """Only verified net realized profit qualifies; phase two requires phase one."""
    if isinstance(phase, bool) or phase not in (1, 2):
        raise ValueError("phase must be 1 or 2")
    if not isinstance(risk, RiskDecision):
        raise TypeError("risk must be a RiskDecision")
    capital = _positive(account_capital, "account_capital")
    profit = dec(realized_net_profit)
    days = _days(trading_days, "trading_days")
    rate = POLICY.phase_one_goal_pct if phase == 1 else POLICY.phase_two_goal_pct
    goal = percent(capital, rate)
    reasons = list(risk.reasons)
    if risk.allowed is not True:
        reasons.append("risk_assessment_not_allowed")
    if phase == 2 and prior_phase_passed is not True:
        reasons.append("phase_one_pass_required")
    if evidence_verified is not True:
        reasons.append("reconciled_evidence_required")
    from .social_policy import LEGACY_CONTRACT_VERSION, NEW_CONTRACT_VERSION
    version = POLICY.version if contract_version is None else contract_version
    if version not in (LEGACY_CONTRACT_VERSION, NEW_CONTRACT_VERSION):
        raise ValueError("Unknown immutable challenge contract version")
    if version == NEW_CONTRACT_VERSION and phase == 2:
        if social_posts_verified is not True:
            reasons.append("social_single_post_each_platform_unverified")
        trades = _days(verified_cumulative_trades, "verified_cumulative_trades")
        if trades < POLICY.min_closed_trades_per_challenge:
            reasons.append("minimum_50_distinct_closed_trades_not_met")
    if days < POLICY.min_challenge_days:
        reasons.append("minimum_trading_days_not_met")
    if profit < goal:
        reasons.append("profit_target_not_met")
    reasons.extend(_consistency_reasons(verified_profit=profit, max_profitable_day=max_profitable_day))
    return ChallengeDecision(not reasons, tuple(dict.fromkeys(reasons)), goal, profit)

def assess_promotion(*, level_index, realized_monthly_profit, trading_days,
                     max_profitable_day, risk, evidence_verified=False,
                     funding_for_next_level=False):
    """One tier each complete period; caller verifies accounting window and funding."""
    if isinstance(level_index, bool) or not isinstance(level_index, int) or not 0 <= level_index < len(LEVELS):
        raise ValueError("invalid level index")
    if not isinstance(risk, RiskDecision):
        raise TypeError("risk must be a RiskDecision")
    profit = dec(realized_monthly_profit)
    days = _days(trading_days, "trading_days")
    current = LEVELS[level_index]
    nxt = LEVELS[min(level_index + 1, len(LEVELS) - 1)]
    reasons = list(risk.reasons)
    if risk.allowed is not True:
        reasons.append("risk_assessment_not_allowed")
    if level_index == len(LEVELS) - 1:
        reasons.append("maximum_level_reached")
    if evidence_verified is not True:
        reasons.append("reconciled_evidence_required")
    if profit < percent(current, POLICY.promotion_goal_pct):
        reasons.append("monthly_profit_target_not_met")
    if days < POLICY.promotion_min_days:
        reasons.append("minimum_trading_days_not_met")
    reasons.extend(_consistency_reasons(verified_profit=profit, max_profitable_day=max_profitable_day))
    if funding_for_next_level is not True:
        reasons.append("next_level_funding_not_confirmed")
    return PromotionDecision(not reasons, tuple(dict.fromkeys(reasons)), current, nxt)

def calculate_payout(*, cumulative_realized_net_profit, previously_allocated_profit):
    """Loss-recovery high-water calculation, NOT an actual transfer command.

    Persist new_allocated_high_water_usd atomically with a unique settlement key.
    """
    pnl = dec(cumulative_realized_net_profit)
    prior = _nonnegative(previously_allocated_profit, "previously_allocated_profit")
    eligible = max(D("0"), pnl - prior).quantize(CENT, rounding=ROUND_DOWN)
    trader = percent(eligible, POLICY.trader_profit_share_pct).quantize(CENT, rounding=ROUND_DOWN)
    return Payout(eligible, trader, eligible - trader, prior + eligible)

def authorize_funding(*, requested_capital, unencumbered_cash,
                      payout_reserve, legal_approved=False, broker_approved=False,
                      kyc_approved=False, contracts_signed=False):
    """Prospective fully funded account gate; caller supplies trusted approvals."""
    capital = _positive(requested_capital, "requested_capital")
    cash = _nonnegative(unencumbered_cash, "unencumbered_cash")
    reserve = _nonnegative(payout_reserve, "payout_reserve")
    need = capital + reserve
    reasons = []
    if capital not in LEVELS:
        reasons.append("unsupported_capital_tier")
    if cash < need:
        reasons.append("unencumbered_capital_insufficient")
    if legal_approved is not True:
        reasons.append("legal_authorization_missing")
    if broker_approved is not True:
        reasons.append("broker_contract_missing")
    if kyc_approved is not True:
        reasons.append("kyc_missing")
    if contracts_signed is not True:
        reasons.append("client_contract_missing")
    return FundingDecision(not reasons, tuple(reasons), need)

def authorize_order(*, account_capital, equity, day_open_equity,
                    risk_at_stop, open_risk_before, broker_minimum_risk,
                    verified_stop=False, authoritative_snapshot=False,
                    mode="real", execution_authorized=False):
    """Fail-closed preflight without broker operations or payment side effects."""
    if mode not in ("real", "challenge"):
        raise ValueError("invalid mode")
    capital = _positive(account_capital, "account_capital")
    single = _nonnegative(risk_at_stop, "risk_at_stop")
    aggregate = _nonnegative(open_risk_before, "open_risk_before")
    minimum = _nonnegative(broker_minimum_risk, "broker_minimum_risk")
    state = assess_risk(account_capital=capital, equity=equity, day_open_equity=day_open_equity)
    reasons = list(state.reasons)
    if capital not in LEVELS:
        reasons.append("unsupported_capital_tier")
    if authoritative_snapshot is not True:
        reasons.append("authoritative_broker_snapshot_required")
    if verified_stop is not True:
        reasons.append("stop_loss_required")
    if single == 0 or single > percent(capital, POLICY.order_risk_pct):
        reasons.append("per_order_risk_limit")
    if aggregate + single > percent(capital, POLICY.aggregate_risk_pct):
        reasons.append("aggregate_risk_limit")
    # Static 0.8% / 1.6% caps do not protect a challenge that has already
    # consumed nearly all of its 4% daily or 8% total drawdown allowance.
    # The authoritative equity mark includes current floating P&L. The
    # aggregate known loss-at-stop (existing positions + proposed order)
    # must leave equity STRICTLY above both breach floors even at stop-out.
    # This does not promise fills at stop: broker slippage/fees must already
    # be included in the signed risk-at-stop inputs.
    projected_equity_at_stop = dec(equity) - aggregate - single
    if projected_equity_at_stop <= max(
            state.daily_equity_floor, state.total_equity_floor):
        reasons.append("stop_risk_exceeds_drawdown_headroom")
    if minimum > single:
        reasons.append("broker_minimum_lot_not_feasible")
    if mode == "real" and (execution_authorized is not True or POLICY.real_orders_enabled is not True):
        reasons.append("real_execution_disabled")
    return RiskDecision(not reasons, tuple(dict.fromkeys(reasons)),
                        state.daily_equity_floor, state.total_equity_floor)

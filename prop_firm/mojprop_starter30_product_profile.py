"""Non-payment product profile for the English MOJ PROP Starter30 offer.

This is an internal operational specification, not a legal contract. It has no
runtime mutation path and cannot enable checkout, create invoices, or custody
customer funds.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal
from datetime import date, timedelta
from collections.abc import Mapping


@dataclass(frozen=True)
class MojPropStarter30Profile:
    product_code: str
    virtual_capital_usd: Decimal
    challenge_duration_days: int
    daily_drawdown_pct: Decimal
    per_trade_risk_pct: Decimal
    open_positions_risk_pct: Decimal
    entry_fee_trx: int
    retry_discount_pct: Decimal
    retry_fee_trx: int
    best_day_profit_share_cap_pct: Decimal
    simulation_only: bool
    customer_funds_custodied: bool
    profit_guarantee: bool
    performance_rewards_real: bool
    consistency_rule_finalized: bool


DEFAULT_STARTER30_PROFILE = MojPropStarter30Profile(
    product_code="mojprop-starter30",
    virtual_capital_usd=Decimal("1000"),
    challenge_duration_days=60,
    daily_drawdown_pct=Decimal("6"),
    per_trade_risk_pct=Decimal("3"),
    open_positions_risk_pct=Decimal("4"),
    entry_fee_trx=30,
    retry_discount_pct=Decimal("40"),
    retry_fee_trx=18,
    # The best trading day may contribute at most 50% of total net profit
    # counted at evaluation; this is an internal product rule.
    best_day_profit_share_cap_pct=Decimal("50"),
    simulation_only=True,
    customer_funds_custodied=False,
    profit_guarantee=False,
    performance_rewards_real=True,
    consistency_rule_finalized=True,
)


def validate_starter30_profile(
    profile: MojPropStarter30Profile = DEFAULT_STARTER30_PROFILE,
) -> tuple[str, ...]:
    """Return blocking profile errors; never changes runtime controls."""
    errors: list[str] = []
    if profile.simulation_only is not True:
        errors.append("simulation_mode_required")
    if profile.customer_funds_custodied is not False:
        errors.append("customer_funds_must_not_be_custodied")
    if profile.profit_guarantee is not False:
        errors.append("profit_guarantee_forbidden")
    if profile.virtual_capital_usd != Decimal("1000"):
        errors.append("virtual_capital_must_equal_1000_usd")
    if profile.challenge_duration_days != 60:
        errors.append("challenge_duration_must_equal_60_days")
    if profile.daily_drawdown_pct != Decimal("6"):
        errors.append("daily_drawdown_must_equal_6_percent")
    if profile.per_trade_risk_pct != Decimal("3"):
        errors.append("per_trade_risk_must_equal_3_percent")
    if profile.open_positions_risk_pct != Decimal("4"):
        errors.append("open_positions_risk_must_equal_4_percent")
    if profile.entry_fee_trx != 30:
        errors.append("entry_fee_must_equal_30_trx")
    if profile.retry_discount_pct != Decimal("40"):
        errors.append("retry_discount_must_equal_40_percent")
    if profile.retry_fee_trx != 18:
        errors.append("retry_fee_must_equal_18_trx")
    if profile.best_day_profit_share_cap_pct != Decimal("50"):
        errors.append("best_day_profit_cap_must_equal_50_percent")
    if profile.consistency_rule_finalized is not True:
        errors.append("consistency_rule_not_finalized")
    return tuple(errors)


@dataclass(frozen=True)
class Starter30ConsistencyDecision:
    allowed: bool
    reasons: tuple[str, ...]
    net_profit_usd: Decimal
    best_day_net_profit_usd: Decimal
    cap_pct: Decimal


def _exact_usd_cents(value: Decimal) -> int:
    """Strict finite USD cents within the isolated account money-field range."""
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError("USD amounts must be finite Decimal values")
    if value.copy_abs() > Decimal("9999999999999999.99"):
        raise ValueError("USD amount exceeds the supported range")
    fixed = value.quantize(Decimal("0.01"), context=Context(prec=32))
    if fixed != value:
        raise ValueError("USD amount must be exact cents")
    sign, digits, exponent = fixed.as_tuple()
    assert exponent == -2
    cents = int("".join(map(str, digits)))
    return -cents if sign else cents


def assess_starter30_consistency(
    *,
    daily_realized_net_usd: Mapping[date, Decimal],
    reconciled_realized_net_usd: Decimal,
    challenge_start_day: date,
    evaluated_through_day: date,
) -> Starter30ConsistencyDecision:
    """Apply only Starter30's finalized 50% best-day rule.

    Inputs are daily net realized P&L after applicable costs, bucketed using
    the applicable challenge day definition. Every calendar bucket in the
    inclusive evaluation window must be supplied, including explicit zeroes
    for verified days with no realized P&L. The window boundaries must be
    independently derived by the caller, not accepted from a customer.
    They must be derived from a
    trusted reconciled execution ledger by the caller. This pure arithmetic
    does not authenticate that ledger, authorize a challenge pass, persist an
    account state, create a reward commitment or transfer money. It is not
    the legacy multi-plan consistency rule.
    """
    profile = DEFAULT_STARTER30_PROFILE
    if validate_starter30_profile(profile):
        raise ValueError("Starter30 profile invalid")
    if not isinstance(daily_realized_net_usd, Mapping):
        raise ValueError("daily realized results must be a dated mapping")
    if type(challenge_start_day) is not date or type(evaluated_through_day) is not date:
        raise ValueError("evaluation boundaries must be calendar dates")
    elapsed = (evaluated_through_day - challenge_start_day).days + 1
    if not 1 <= elapsed <= profile.challenge_duration_days:
        raise ValueError("evaluation window must be within 60 calendar buckets")
    expected_days = {challenge_start_day + timedelta(days=i) for i in range(elapsed)}
    if len(daily_realized_net_usd) > elapsed:
        raise ValueError("daily result count exceeds the evaluation window")
    total = _exact_usd_cents(reconciled_realized_net_usd)
    daily = []
    for trading_day, pnl in daily_realized_net_usd.items():
        if type(trading_day) is not date:
            raise ValueError("each daily bucket must be a calendar date")
        if trading_day not in expected_days:
            raise ValueError("daily result outside the evaluation window")
        daily.append(_exact_usd_cents(pnl))
    best = max([0] + daily)
    reasons = []
    if set(daily_realized_net_usd) != expected_days:
        reasons.append("daily_evidence_missing")
    if sum(daily) != total:
        reasons.append("daily_net_profit_reconciliation_mismatch")
    if total <= 0:
        reasons.append("positive_net_profit_required")
    elif best * 100 > total * int(profile.best_day_profit_share_cap_pct):
        reasons.append("starter30_profit_consistency_not_met")
    return Starter30ConsistencyDecision(
        not reasons, tuple(reasons), reconciled_realized_net_usd,
        Decimal(f'{best // 100}.{best % 100:02d}'), profile.best_day_profit_share_cap_pct,
    )

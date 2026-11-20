"""Non-payment product profile for the English MOJ PROP Starter30 offer.

This is an internal operational specification, not a legal contract. It has no
runtime mutation path and cannot enable checkout, create invoices, or custody
customer funds.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


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
    simulation_only=True,
    customer_funds_custodied=False,
    profit_guarantee=False,
    performance_rewards_real=True,
    # The public consistency rule still requires business/legal confirmation.
    consistency_rule_finalized=False,
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
    if profile.consistency_rule_finalized is not True:
        errors.append("consistency_rule_not_finalized")
    return tuple(errors)

"""Broker-fit decision for the $100 real-account tier and all 14 capital levels.

Inputs must come from the authenticated broker symbol specification and a
fresh quote/stop calculation. This module does not fetch quotes or send orders.
It never adjusts the stop-loss to manufacture a feasible trade.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

from .rules import POLICY, LEVELS, dec, percent


class BrokerFitError(ValueError):
    pass


@dataclass(frozen=True)
class BrokerFit:
    feasible: bool
    reasons: tuple[str, ...]
    capital_usd: Decimal
    order_risk_budget_usd: Decimal
    aggregate_risk_budget_usd: Decimal
    broker_min_quantity: Decimal
    minimum_trade_loss_usd: Decimal
    total_margin_needed_usd: Decimal


def _positive(value, field):
    try:
        n = dec(value)
    except (ValueError, TypeError) as exc:
        raise BrokerFitError(f"{field} requires an exact finite decimal") from exc
    if n <= 0:
        raise BrokerFitError(f"{field} must be positive")
    return n


def _nonnegative(value, field):
    try:
        n = dec(value)
    except (ValueError, TypeError) as exc:
        raise BrokerFitError(f"{field} requires an exact finite decimal") from exc
    if n < 0:
        raise BrokerFitError(f"{field} must not be negative")
    return n


def check_minimum_broker_order(*, tier_index, broker_min_quantity,
                               broker_quantity_step,
                               stop_loss_usd_per_unit,
                               round_trip_fees_usd,
                               margin_usd_per_unit,
                               available_margin_usd,
                               currently_open_risk_usd=0,
                               quote_verified=False,
                               stop_verified=False,
                               specification_verified=False):
    """Fail closed on uncertain broker specs, spreads/fees, and aggregate risk."""
    if isinstance(tier_index, bool) or not isinstance(tier_index, int):
        raise BrokerFitError("Invalid tier index")
    try:
        capital = LEVELS[tier_index]
    except IndexError as exc:
        raise BrokerFitError("Tier outside 14-level ladder") from exc
    if tier_index < 0:
        raise BrokerFitError("Tier outside 14-level ladder")

    minimum = _positive(broker_min_quantity, "broker_min_quantity")
    step = _positive(broker_quantity_step, "broker_quantity_step")
    loss_per_unit = _positive(stop_loss_usd_per_unit, "stop_loss_usd_per_unit")
    fees = _nonnegative(round_trip_fees_usd, "round_trip_fees_usd")
    margin_per_unit = _positive(margin_usd_per_unit, "margin_usd_per_unit")
    margin_available = _nonnegative(available_margin_usd, "available_margin_usd")
    open_risk = _nonnegative(currently_open_risk_usd, "currently_open_risk_usd")

    # Conservative rounding upward to the actual broker unit step.
    lots = (minimum / step).to_integral_value(rounding=ROUND_CEILING)
    trade_quantity = lots * step
    stop_risk = loss_per_unit * trade_quantity
    total_loss = stop_risk + fees
    margin = margin_per_unit * trade_quantity
    order_limit = percent(capital, POLICY.order_risk_pct)
    aggregate_limit = percent(capital, POLICY.aggregate_risk_pct)
    errors = []
    if not all((quote_verified is True, stop_verified is True,
                specification_verified is True)):
        errors.append("fresh_verified_broker_spec_quote_stop_required")
    if total_loss <= 0 or total_loss > order_limit:
        errors.append("minimum_order_exceeds_single_trade_risk")
    if open_risk + total_loss > aggregate_limit:
        errors.append("minimum_order_exceeds_aggregate_risk")
    if margin > margin_available:
        errors.append("margin_unavailable_for_broker_minimum")
    return BrokerFit(
        feasible=not errors,
        reasons=tuple(errors),
        capital_usd=capital,
        order_risk_budget_usd=order_limit,
        aggregate_risk_budget_usd=aggregate_limit,
        broker_min_quantity=trade_quantity,
        minimum_trade_loss_usd=total_loss,
        total_margin_needed_usd=margin,
    )

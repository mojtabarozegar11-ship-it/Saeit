"""Draft-only MOJ-PROP-01 XAUUSD 3% / 8% policy bridge.

Additive to the v1.2 core. Does not alter customer agreements, turn on orders,
settle TRX, attest broker snapshots, or grant funded account entitlements.
Inputs must eventually come from an authenticated reconciled broker adapter;
caller-supplied booleans are not independent verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from .rules import POLICY, LEVELS
from .plans import CHALLENGE_PLANS

DRAFT_CONTRACT_VERSION = "2026-11-17/v1.3-XAUUSD-DRAFT"
LEGACY_CONTRACT_VERSION = "2026-11-15/v1.2"
PRODUCT = "MOJ-PROP-01"
INSTRUMENT = "XAUUSD"
MAX_QUOTE_AGE = timedelta(minutes=5)


def exact(value, *, allow_zero=False):
    if type(value) not in (str, Decimal, int) or len(str(value)) > 128:
        raise ValueError("exact, bounded decimal required")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid decimal") from exc
    if not number.is_finite():
        raise ValueError("non-finite risk input")
    if (len(number.as_tuple().digits) > 28 or
            not -18 <= number.as_tuple().exponent <= 18):
        raise ValueError("decimal precision or exponent exceeds risk-input bounds")
    if (number < 0 or
            number > Decimal("1000000000") or (number == 0 and not allow_zero)):
        raise ValueError("invalid nonnegative bounded amount")
    return number


@dataclass(frozen=True)
class GoldOrderSnapshot:
    product: str
    contract_version: str
    symbol: str
    account_currency: str
    initial_capital: str
    equity: str
    day_open_equity: str
    existing_open_remaining_stop_risk: str
    side: str
    mid_price_per_oz: str
    stop_price_per_oz: str
    lot_quantity: str
    minimum_lot: str
    lot_step: str
    ounces_per_lot: str
    min_stop_distance_per_oz: str
    full_spread_per_oz: str
    slippage_reserve_per_oz: str
    roundtrip_fees_usd: str
    margin_required_usd: str
    free_margin_usd: str
    quote_at: datetime
    assessed_at: datetime
    broker_snapshot_claimed: bool = False
    complete_open_positions_claimed: bool = False
    symbol_spec_claimed: bool = False
    stop_claimed: bool = False


@dataclass(frozen=True)
class GoldReview:
    mathematically_admissible: bool
    reasons: tuple[str, ...]
    order_risk_usd: Decimal
    open_risk_usd: Decimal
    max_single_usd: Decimal
    max_open_usd: Decimal
    daily_equity_floor: Decimal
    total_equity_floor: Decimal
    independent_broker_verified: bool = False
    real_orders_enabled: bool = False
    checkout_enabled: bool = False
    funding_enabled: bool = False
    contract_binding_enabled: bool = False


def review_gold_order(snapshot: GoldOrderSnapshot) -> GoldReview:
    """Offline mathematical review; never places orders or approves customers."""
    if not isinstance(snapshot, GoldOrderSnapshot):
        raise TypeError("immutable snapshot required")
    # This bridge is deliberately tied to the currently reviewed v1.2 base.
    # No silent migration of existing customer contracts or policy rewriting.
    if (POLICY.version != LEGACY_CONTRACT_VERSION or
            POLICY.order_risk_pct != Decimal("0.8") or
            POLICY.aggregate_risk_pct != Decimal("1.6") or
            POLICY.max_daily_loss_pct != Decimal("4") or
            POLICY.max_total_loss_pct != Decimal("8") or
            POLICY.real_orders_enabled is not False or
            POLICY.trx_checkout_enabled is not False or
            LEVELS[0] != Decimal("100") or
            CHALLENGE_PLANS[0].code != PRODUCT):
        raise RuntimeError("unexpected canonical policy; re-review required")
    if snapshot.product != PRODUCT or snapshot.contract_version != DRAFT_CONTRACT_VERSION:
        raise ValueError("only proposed new contract; legacy v1.2 unchanged")
    reasons = []
    if snapshot.symbol != INSTRUMENT or snapshot.account_currency != "USD":
        reasons.append("xauusd_usd_only")
    if snapshot.side not in ("buy", "sell"):
        reasons.append("invalid_trade_side")
    if not all(value is True for value in (
        snapshot.broker_snapshot_claimed, snapshot.complete_open_positions_claimed,
        snapshot.symbol_spec_claimed, snapshot.stop_claimed,
    )):
        reasons.append("unreconciled_snapshot_claims")
    if (type(snapshot.quote_at) is not datetime or
            type(snapshot.assessed_at) is not datetime or
            snapshot.quote_at.tzinfo is None or snapshot.assessed_at.tzinfo is None or
            snapshot.quote_at.utcoffset() is None or snapshot.assessed_at.utcoffset() is None):
        reasons.append("timezone_aware_quote_required")
    else:
        age = snapshot.assessed_at.astimezone(timezone.utc) - snapshot.quote_at.astimezone(timezone.utc)
        if not timedelta(0) <= age <= MAX_QUOTE_AGE:
            reasons.append("stale_or_future_quote")

    capital = exact(snapshot.initial_capital)
    equity = exact(snapshot.equity, allow_zero=True)
    day_open = exact(snapshot.day_open_equity)
    existing = exact(snapshot.existing_open_remaining_stop_risk, allow_zero=True)
    entry = exact(snapshot.mid_price_per_oz)
    stop = exact(snapshot.stop_price_per_oz)
    lot = exact(snapshot.lot_quantity)
    minimum = exact(snapshot.minimum_lot)
    step = exact(snapshot.lot_step)
    ounces = exact(snapshot.ounces_per_lot)
    min_stop = exact(snapshot.min_stop_distance_per_oz, allow_zero=True)
    spread = exact(snapshot.full_spread_per_oz, allow_zero=True)
    slippage = exact(snapshot.slippage_reserve_per_oz, allow_zero=True)
    fees = exact(snapshot.roundtrip_fees_usd, allow_zero=True)
    margin = exact(snapshot.margin_required_usd)
    free_margin = exact(snapshot.free_margin_usd, allow_zero=True)
    if capital != Decimal("100"):
        reasons.append("plan1_initial_capital_only")
    if lot < minimum or (lot / step) != (lot / step).to_integral_value():
        reasons.append("broker_lot_step_rejected")
    if ((snapshot.side == "buy" and stop >= entry) or
            (snapshot.side == "sell" and stop <= entry)):
        reasons.append("stop_on_wrong_side")
    if abs(entry - stop) < min_stop:
        reasons.append("broker_min_stop_distance_rejected")
    if margin > free_margin:
        reasons.append("insufficient_verified_free_margin")

    # Conservative all-in adverse move from a mid-price reference.
    # Broker-side stop fills are not guaranteed; this is not a risk guarantee.
    trade_loss = lot * ounces * (abs(entry - stop) + spread + slippage) + fees
    open_loss = existing + trade_loss
    single_cap = capital * Decimal("0.03")
    aggregate_cap = capital * Decimal("0.08")
    daily_floor = day_open - capital * Decimal("0.04")
    total_floor = capital * Decimal("0.92")
    if trade_loss <= 0 or trade_loss > single_cap:
        reasons.append("trade_exceeds_3pct")
    if open_loss > aggregate_cap:
        reasons.append("open_positions_exceed_8pct")
    if equity <= daily_floor or equity <= total_floor:
        reasons.append("account_already_at_drawdown_limit")
    if equity - open_loss <= max(daily_floor, total_floor):
        reasons.append("projected_stops_breach_drawdown_limit")
    return GoldReview(
        mathematically_admissible=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
        order_risk_usd=trade_loss,
        open_risk_usd=open_loss,
        max_single_usd=single_cap,
        max_open_usd=aggregate_cap,
        daily_equity_floor=daily_floor,
        total_equity_floor=total_floor,
    )

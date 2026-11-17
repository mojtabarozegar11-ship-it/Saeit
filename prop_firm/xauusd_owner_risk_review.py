"""Exact XAUUSD owner-request risk proposal; review-only, with NO broker side effects.

This module does not modify the existing signed v1.2 policy, does not enable
trading, and never issues an order. The proposed 3% single/8% open caps are
ceilings, not entitlements: stop-out exposure (including fees and slippage)
must also remain STRICTLY above the 4% daily and 8% total loss floors.
Caller-provided broker/contract evidence must originate in a separate trusted
adapter. Passing this offline review does not authorize an order or funding.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .rules import POLICY, LEVELS, dec, percent

D = Decimal
SYMBOL = "XAUUSD"
PROPOSAL_VERSION = "OWNER-XAUUSD-RISK-REVIEW-2026-11-17"
MAX_SINGLE_PERCENT = D("3")
MAX_OPEN_PERCENT = D("8")


@dataclass(frozen=True)
class XAUUSDRiskReview:
    math_and_evidence_ready: bool
    reasons: tuple[str, ...]
    proposed_single_ceiling_usd: Decimal
    proposed_open_ceiling_usd: Decimal
    daily_equity_floor_usd: Decimal
    total_equity_floor_usd: Decimal
    projected_equity_at_stop_usd: Decimal
    version: str = PROPOSAL_VERSION
    real_execution_authorized: bool = False
    challenge_order_submitted: bool = False
    payment_or_funding_authorized: bool = False


def _nonnegative_decimal(value, name):
    v = dec(value)
    if v < 0:
        raise ValueError(f"{name} must be nonnegative")
    return v


def review_owner_xauusd_risk(
    *, symbol, account_capital, equity, day_open_equity,
    proposed_order_risk_at_stop, existing_open_risk_at_stop,
    extra_fee_slippage_reserve, broker_minimum_risk,
    stop_server_verified=False, broker_snapshot_verified=False,
    broker_lot_verified=False, operative_terms_reconciled=False,
    mode="challenge",
):
    """Pure arithmetic and source-authentication flags; zero real-world writes.

    The risk inputs must already be independent broker-reconciled monetary
    estimates, including adverse gap/slippage and commissions for all open
    positions. The additional non-zero reserve covers uncertainty for the
    proposed order; it cannot be omitted or treated as measured fill quality.
    """
    if type(symbol) is not str or type(mode) is not str:
        raise ValueError("symbol and mode must be exact strings")
    if mode not in ("challenge", "real"):
        raise ValueError("invalid mode")
    capital = dec(account_capital)
    if capital <= 0:
        raise ValueError("capital must be positive")
    equity_now = _nonnegative_decimal(equity, "equity")
    day_open = _nonnegative_decimal(day_open_equity, "day_open_equity")
    order = _nonnegative_decimal(proposed_order_risk_at_stop, "proposed_order_risk_at_stop")
    open_risk = _nonnegative_decimal(existing_open_risk_at_stop, "existing_open_risk_at_stop")
    reserve = _nonnegative_decimal(extra_fee_slippage_reserve, "extra_fee_slippage_reserve")
    broker_min = _nonnegative_decimal(broker_minimum_risk, "broker_minimum_risk")

    per_order_limit = percent(capital, MAX_SINGLE_PERCENT)
    open_limit = percent(capital, MAX_OPEN_PERCENT)
    daily_floor = day_open - percent(capital, POLICY.max_daily_loss_pct)
    total_floor = capital - percent(capital, POLICY.max_total_loss_pct)
    at_stop = equity_now - (open_risk + order + reserve)
    reasons = []

    if symbol != SYMBOL:
        reasons.append("xauusd_only")
    if capital not in LEVELS:
        reasons.append("unsupported_account_tier")
    if order <= 0 or order > per_order_limit:
        reasons.append("proposed_single_cap_exceeded")
    if open_risk + order > open_limit:
        reasons.append("proposed_aggregate_cap_exceeded")
    if reserve <= 0:
        reasons.append("positive_slippage_reserve_required")
    if broker_min > order:
        reasons.append("broker_min_lot_risk_exceeds_order")
    if equity_now <= daily_floor:
        reasons.append("already_breached_daily_floor")
    if equity_now <= total_floor:
        reasons.append("already_breached_total_floor")
    if at_stop <= daily_floor:
        reasons.append("projected_stop_breaches_daily_floor")
    if at_stop <= total_floor:
        reasons.append("projected_stop_breaches_total_floor")

    required = (
        (stop_server_verified, "trusted_stop_missing"),
        (broker_snapshot_verified, "authoritative_broker_snapshot_missing"),
        (broker_lot_verified, "broker_lot_not_verified"),
        (operative_terms_reconciled, "signed_terms_policy_conflict_unresolved"),
    )
    for value, reason in required:
        if value is not True:
            reasons.append(reason)
    if mode == "real":
        reasons.append("real_execution_not_enabled_by_review")

    return XAUUSDRiskReview(
        math_and_evidence_ready=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
        proposed_single_ceiling_usd=per_order_limit,
        proposed_open_ceiling_usd=open_limit,
        daily_equity_floor_usd=daily_floor,
        total_equity_floor_usd=total_floor,
        projected_equity_at_stop_usd=at_stop,
    )

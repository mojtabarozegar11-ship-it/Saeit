"""Owner-held LiteFinance risk admission: pure, non-executing review only.

Inputs must be constructed by an authenticated server from reconciled broker
and internal ledger data, never from browser-supplied balances or permissions.
An allowed preview is NOT an order authorization or a capital reservation.
The production adapter must re-read and atomically reserve under an account
lock before submitting anything; uncertain broker outcomes retain reservations.
"""
from dataclasses import dataclass
from decimal import Decimal
import re

from .rules import LEVELS, POLICY, assess_risk, percent

REF = re.compile(r"[A-Za-z0-9_-]{8,96}\Z")
REQUIRED_EVIDENCE = (
    "broker_delegation_approved",
    "owner_account_control_verified",
    "both_demo_passes_verified",
    "trader_eligible_and_active",
    "signed_current_terms_verified",
    "owner_funding_allocatable_verified",
    "complete_broker_positions_reconciled",
    "all_pending_orders_and_reservations_reconciled",
    "fresh_quote_stop_and_costs_verified",
    "broker_quantity_and_margin_verified",
    "independent_trader_attribution_verified",
)


@dataclass(frozen=True)
class Compartment:
    trader_ref: str
    tier_index: int
    equity_usd: Decimal
    day_open_equity_usd: Decimal
    open_and_reserved_risk_usd: Decimal


@dataclass(frozen=True)
class RiskPreview:
    review_allowed: bool
    reasons: tuple[str, ...]
    allocated_capital_usd: Decimal
    aggregate_open_and_reserved_risk_usd: Decimal
    proposed_order_risk_usd: Decimal
    trader_order_limit_usd: Decimal
    trader_aggregate_limit_usd: Decimal
    account_aggregate_limit_usd: Decimal
    broker_order_authorized: bool = False
    capital_reserved: bool = False
    order_submitted: bool = False


def _amount(value, name, positive=False):
    if (type(value) is not Decimal or not value.is_finite()
            or value < 0 or (positive and value == 0)
            or value > Decimal("1000000000000")
            or value.as_tuple().exponent < -8):
        raise ValueError(f"invalid exact USD amount: {name}")
    return value


def _ref(value):
    if type(value) is not str or REF.fullmatch(value) is None:
        raise ValueError("invalid internal trader reference")
    return value


def preview_owner_account_order(*, compartments, authenticated_trader_ref,
                                requested_trader_ref, verified_owner_capital_usd,
                                broker_equity_usd, broker_day_open_equity_usd,
                                broker_free_margin_usd,
                                other_account_open_and_reserved_risk_usd,
                                proposed_all_in_stop_risk_usd,
                                proposed_margin_usd, evidence):
    """Review prospective order risk against trader and whole-account limits.

    The same capital cannot be allocated twice. Include open and pending
    orders, non-program exposures and reserved risk. The account limits use
    canonical percentages conservatively on verified owner capital, not on
    customer deposits, inflated virtual tiers or unrealized gains.
    A real broker order can incur losses beyond a stop estimate.
    """
    if type(evidence) is not dict or set(evidence) != set(REQUIRED_EVIDENCE):
        raise ValueError("complete authenticated evidence set required")
    if type(compartments) is not tuple or not 1 <= len(compartments) <= 10000:
        raise ValueError("complete bounded compartment snapshot required")
    auth = _ref(authenticated_trader_ref)
    requested = _ref(requested_trader_ref)
    capital = _amount(verified_owner_capital_usd, "capital", True)
    equity = _amount(broker_equity_usd, "broker equity")
    day_open = _amount(broker_day_open_equity_usd, "broker day open")
    margin = _amount(broker_free_margin_usd, "available margin")
    other = _amount(other_account_open_and_reserved_risk_usd, "other risk")
    risk = _amount(proposed_all_in_stop_risk_usd, "order risk", True)
    needed = _amount(proposed_margin_usd, "order margin", True)
    refs = set()
    allocated = Decimal("0")
    total_risk = other
    selected = None
    reasons = [key for key in REQUIRED_EVIDENCE if evidence[key] is not True]
    if auth != requested:
        reasons.append("cross_trader_request")
    for row in compartments:
        if type(row) is not Compartment:
            raise ValueError("invalid compartment")
        key = _ref(row.trader_ref)
        if key in refs:
            raise ValueError("duplicate trader allocation")
        refs.add(key)
        if type(row.tier_index) is not int or not 0 <= row.tier_index < len(LEVELS):
            raise ValueError("invalid allocation tier")
        tier = LEVELS[row.tier_index]
        _amount(row.equity_usd, "trader equity")
        _amount(row.day_open_equity_usd, "trader day open")
        existing = _amount(row.open_and_reserved_risk_usd, "trader risk")
        allocated += tier
        total_risk += existing
        if key == auth:
            selected = row
    if selected is None:
        reasons.append("trader_allocation_missing")
        tier = Decimal("0")
        existing = Decimal("0")
    else:
        tier = LEVELS[selected.tier_index]
        existing = selected.open_and_reserved_risk_usd
        trial = assess_risk(account_capital=tier,
                            equity=selected.equity_usd,
                            day_open_equity=selected.day_open_equity_usd)
        reasons.extend("trader_" + x for x in trial.reasons)
        if selected.equity_usd - existing - risk <= max(
                trial.daily_equity_floor, trial.total_equity_floor):
            reasons.append("trader_projected_loss_floor_reached")
    if allocated > min(capital, equity):
        reasons.append("owner_capital_overallocated")
    account = assess_risk(account_capital=capital, equity=equity,
                          day_open_equity=day_open)
    reasons.extend("account_" + x for x in account.reasons)
    if equity - total_risk - risk <= max(account.daily_equity_floor, account.total_equity_floor):
        reasons.append("account_projected_loss_floor_reached")
    single = percent(tier, POLICY.order_risk_pct)
    trader_limit = percent(tier, POLICY.aggregate_risk_pct)
    account_limit = percent(capital, POLICY.aggregate_risk_pct)
    if risk > single:
        reasons.append("trader_single_order_limit")
    if existing + risk > trader_limit:
        reasons.append("trader_aggregate_risk_limit")
    if total_risk + risk > account_limit:
        reasons.append("owner_account_aggregate_risk_limit")
    if needed > margin:
        reasons.append("broker_free_margin_insufficient")
    return RiskPreview(not reasons, tuple(reasons), allocated, total_risk,
                       risk, single, trader_limit, account_limit)

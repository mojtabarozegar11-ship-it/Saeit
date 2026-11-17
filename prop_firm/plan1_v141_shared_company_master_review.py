"""MOJ PROP v1.4.1 shared COMPANY broker account — source-only capacity policy.

ARCHITECTURAL CONTRACT:
- Any number of separately identified traders can submit DEMO intentions to
  their own isolated VIRTUAL challenge ledgers; those are NEVER broker orders.
- A single COMPANY-OWNED real broker account MAY eventually be an aggregate
  execution venue, not a customer account or a broker account per trader.
- No trader has LiteFinance credentials or deposits funds into the broker.
- Customer 30 native TRX evaluation fees (if lawfully sold in the future)
  are separate merchant receipts, NEVER brokerage deposits or equity.
- A real master-account order cannot be inferred from a user click. An
  independent legal/broker approval, order router, funding, per-tenant ledger,
  backend risk state, exchange execution receipt and reconciliation are all
  still required. This module cannot issue real or demo broker orders.

This module is deliberately pure; no Django, API, network, wallet, credentials
or storage. It does not change the legacy v1.2 funded-account allocation rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

MAX_REQUESTS = 5000
ACCOUNT_CAPITAL = Decimal("100")
MAX_SINGLE_RISK = Decimal("3")
MAX_AGGREGATE_RISK = Decimal("8")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}\Z")


class CompanyMasterReviewRejected(ValueError):
    """Invalid/unsafe master-account capacity or virtual-trader input."""


def _id(text: str, label: str) -> str:
    if type(text) is not str or _ID.fullmatch(text) is None:
        raise CompanyMasterReviewRejected(label + ": opaque identifier required")
    return text


def _usd(value, label: str, *, positive: bool = False) -> Decimal:
    # Money comes from a trusted internal quotation / risk source, never
    # floating-point browser fields.
    if type(value) not in (str, Decimal, int):
        raise CompanyMasterReviewRejected(label + ": exact decimal required")
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CompanyMasterReviewRejected(label + ": decimal invalid") from exc
    if (not num.is_finite() or abs(num) > Decimal("1000000")
            or num.as_tuple().exponent < -4
            or num < 0 or (positive and num == 0)):
        raise CompanyMasterReviewRejected(label + ": nonnegative bounded four-decimal USD required")
    return num


@dataclass(frozen=True)
class VirtualTraderIntent:
    virtual_trader_ref: str
    virtual_challenge_ref: str
    internal_order_ref: str
    symbol: str
    side: str
    estimated_stop_risk_usd: str
    estimated_margin_usd: str
    # There is intentionally NO broker password, wallet or broker account ID.


@dataclass(frozen=True)
class CompanyMasterSnapshot:
    # One company account reference irrespective of number of website traders.
    company_broker_ref: str
    account_equity_usd: str
    free_margin_usd: str
    existing_risk_at_stop_usd: str
    reserved_pending_risk_usd: str
    # The mode must be independently verified from the actual company account.
    position_accounting_mode: str


@dataclass(frozen=True)
class SharedMasterCapacityReview:
    website_virtual_trader_count: int
    distinct_virtual_challenge_count: int
    company_broker_account_count: int
    aggregate_requested_risk_usd: Decimal
    total_including_existing_risk_usd: Decimal
    remaining_aggregate_risk_usd: Decimal
    margin_requested_usd: Decimal
    capacity_math_within_limits: bool
    reasons: tuple[str, ...]
    # User trade clicks, capacity arithmetic and account references are NOT
    # live order permission or evidence of broker delegation.
    each_trader_has_independent_broker_account: bool = False
    third_party_broker_deposits_needed: bool = False
    direct_trader_broker_login_needed: bool = False
    broker_api_connection_independently_verified: bool = False
    broker_multitenant_routing_contractually_authorized: bool = False
    verified_live_broker_aggregate_state: bool = False
    tenant_pnl_attribution_and_external_reconciliation_verified: bool = False
    live_order_routing_authorized: bool = False
    paid_enrollment_authorized: bool = False
    payout_authorized: bool = False


def review_company_master_capacity(
    *, snapshot: CompanyMasterSnapshot, intents: tuple[VirtualTraderIntent, ...],
) -> SharedMasterCapacityReview:
    """Compute conservative SHARED account aggregate risk, WITHOUT orders.

    Covers one proposed batch only. Callers must obtain a second, atomic,
    trusted server-side preflight for other concurrent batches and pending
    broker orders. A positive result is NOT permission to place a trade.
    """
    if type(snapshot) is not CompanyMasterSnapshot or type(intents) is not tuple:
        raise CompanyMasterReviewRejected("typed company snapshot and immutable order-intent tuple required")
    _id(snapshot.company_broker_ref, "company_broker_ref")
    if snapshot.position_accounting_mode not in ("netting", "hedging"):
        raise CompanyMasterReviewRejected("independently verified netting/hedging setting required")
    equity = _usd(snapshot.account_equity_usd, "equity", positive=True)
    free = _usd(snapshot.free_margin_usd, "free_margin")
    old = _usd(snapshot.existing_risk_at_stop_usd, "existing_risk")
    pending = _usd(snapshot.reserved_pending_risk_usd, "pending_risk")
    if len(intents) > MAX_REQUESTS:
        raise CompanyMasterReviewRejected("bounded batch required")
    seen_orders = set()
    unique_traders = set()
    unique_challenges = set()
    requested = Decimal("0")
    margin = Decimal("0")
    sides = set()
    reasons = []
    for intent in intents:
        if type(intent) is not VirtualTraderIntent:
            raise CompanyMasterReviewRejected("immutable internal trader intent required")
        trader = _id(intent.virtual_trader_ref, "trader")
        challenge = _id(intent.virtual_challenge_ref, "challenge")
        ref = _id(intent.internal_order_ref, "order")
        if ref in seen_orders:
            raise CompanyMasterReviewRejected("duplicate internal order reference")
        seen_orders.add(ref)
        unique_traders.add(trader)
        unique_challenges.add(challenge)
        if intent.symbol != "XAUUSD" or intent.side not in ("BUY", "SELL"):
            raise CompanyMasterReviewRejected("explicit reviewed XAUUSD BUY/SELL only")
        risk = _usd(intent.estimated_stop_risk_usd, "stop_risk", positive=True)
        required = _usd(intent.estimated_margin_usd, "margin", positive=True)
        requested += risk
        margin += required
        sides.add(intent.side)
        if risk > MAX_SINGLE_RISK:
            reasons.append("company_master_single_order_risk_over_3_usd")
    # A 100 USD account with <=8 USD group risk cannot emulate hundreds of
    # independently funded 100 USD real accounts at once. Virtual challenges
    # must remain explicitly distinct from company brokerage execution.
    if equity != ACCOUNT_CAPITAL:
        reasons.append("100_usd_master_account_risk_policy_requires_re_review")
    total = old + pending + requested
    if total > MAX_AGGREGATE_RISK:
        reasons.append("shared_company_account_aggregate_stop_risk_over_8_usd")
    if margin > free:
        reasons.append("company_master_margin_insufficient")
    if snapshot.position_accounting_mode == "netting" and len(sides) == 2:
        reasons.append("opposite_user_orders_need_independent_netting_attribution")
    return SharedMasterCapacityReview(
        website_virtual_trader_count=len(unique_traders),
        distinct_virtual_challenge_count=len(unique_challenges),
        company_broker_account_count=1,
        aggregate_requested_risk_usd=requested,
        total_including_existing_risk_usd=total,
        remaining_aggregate_risk_usd=max(Decimal("0"), MAX_AGGREGATE_RISK - total),
        margin_requested_usd=margin,
        capacity_math_within_limits=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
    )

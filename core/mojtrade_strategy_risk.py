"""Deterministic, research-only MojTrade strategy and portfolio risk review.

This module classifies proven *research stances*, not trade-entry signals. An
hourly public OHLC observation is not a broker quote, executable spread,
contract specification or account statement. No branch can approve an order.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json


MODEL_VERSION = "mojtrade-research-gate-v1"
MAX_RISK_PER_TRADE = Decimal("0.0025")
MAX_DAILY_LOSS = Decimal("0.02")
MAX_AGGREGATE_OPEN_RISK = Decimal("0.01")
CANDIDATE_STANCES = {"watch_buy": "monitor_bullish", "watch_sell": "monitor_bearish"}
RESEARCH_ONLY_BLOCKERS = (
    "live_broker_quote_not_verified",
    "executable_spread_and_slippage_not_verified",
    "instrument_contract_and_stop_distance_not_verified",
    "account_margin_and_portfolio_exposure_not_verified",
    "broker_order_adapter_not_authorized",
)


class MojTradeRiskError(ValueError):
    """Reject unreliable inputs rather than constructing an order intent."""


def _money(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, str)):
        raise MojTradeRiskError(f"{field}_invalid")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MojTradeRiskError(f"{field}_invalid") from exc
    if not number.is_finite():
        raise MojTradeRiskError(f"{field}_nonfinite")
    return number


def assess_account_risk_budget(
    *, equity: object, realized_daily_pnl: object, open_stop_risk: object,
) -> dict:
    """Return conservative loss capacity, NEVER position sizing or trade permission.

    All amounts must be in the *same, explicitly reconciled account currency*.
    Unknown or unverified account inputs must not be supplied as estimates.
    This is a pure offline calculation; no credentials/quotations are accessed.
    """
    balance = _money(equity, "equity")
    pnl = _money(realized_daily_pnl, "realized_daily_pnl")
    reserved = _money(open_stop_risk, "open_stop_risk")
    if balance <= 0 or reserved < 0:
        raise MojTradeRiskError("account_risk_inputs_out_of_range")
    max_day = balance * MAX_DAILY_LOSS
    day_used = max(-pnl, Decimal("0"))
    remaining_day = max(Decimal("0"), max_day - day_used - reserved)
    max_open = balance * MAX_AGGREGATE_OPEN_RISK
    remaining_portfolio = max(Decimal("0"), max_open - reserved)
    per_trade = balance * MAX_RISK_PER_TRADE
    budget = min(per_trade, remaining_day, remaining_portfolio)
    return {
        "version": MODEL_VERSION,
        "risk_currency": "same_reconciled_account_currency_required",
        "max_per_trade_fraction": str(MAX_RISK_PER_TRADE),
        "max_daily_loss_fraction": str(MAX_DAILY_LOSS),
        "max_aggregate_open_risk_fraction": str(MAX_AGGREGATE_OPEN_RISK),
        "per_trade_risk_budget": str(per_trade),
        "daily_loss_remaining": str(remaining_day),
        "portfolio_risk_remaining": str(remaining_portfolio),
        "advisory_capacity": str(budget),
        "risk_capacity_available": budget > 0,
        "broker_data_validated": False,
        "execution_authorized": False,
        "order_quantity": None,
    }


def review_research(report: dict) -> dict:
    """Convert validated observation metadata to a non-executable review.

    Caller must already have validated provenance, TTL, market/source, and
    payload integrity. Refuse any sign of order/execution metadata drift.
    """
    if (
        not isinstance(report, dict)
        or report.get("execution") != "disabled"
        or report.get("orders") != 0
        or report.get("action") != "research_only"
        or report.get("report_type") != "mojtrade-research-observation-consumption"
    ):
        raise MojTradeRiskError("research_only_contract_required")
    signals = report.get("signals")
    if not isinstance(signals, list) or len(signals) != 2:
        raise MojTradeRiskError("research_signal_set_invalid")
    if [x.get("symbol") if isinstance(x, dict) else None for x in signals] != [
        "BTC/USD", "ETH/USD",
    ]:
        raise MojTradeRiskError("research_symbol_set_invalid")

    decisions = []
    for signal in signals:
        stance = signal.get("stance")
        if stance not in {"watch_buy", "watch_sell", "neutral"}:
            raise MojTradeRiskError("research_stance_invalid")
        if any(not isinstance(signal.get(key), str) or not signal.get(key) for key in (
            "id", "observed_at", "data_source", "method",
        )):
            raise MojTradeRiskError("research_signal_provenance_missing")
        classification = CANDIDATE_STANCES.get(stance, "no_setup")
        decisions.append({
            "symbol": signal["symbol"],
            "source_signal_id": signal["id"],
            "source_provider": signal["data_source"],
            "source_observed_at": signal["observed_at"],
            "source_method": signal["method"],
            "classification": classification,
            "setup_candidate": classification != "no_setup",
            "risk_gate": "blocked_missing_broker_verified_inputs",
            "blockers": list(RESEARCH_ONLY_BLOCKERS),
            "order_intent": None,
            "execution_authorized": False,
        })

    fingerprint = hashlib.sha256(json.dumps(
        {"version": MODEL_VERSION, "decisions": decisions},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")).hexdigest()
    return {
        "schema": MODEL_VERSION,
        "strategy_family": "closed_1h_trend_watch_research",
        "decision_digest_sha256": fingerprint,
        "decisions": decisions,
        "setup_candidates_not_trades": sum(x["setup_candidate"] for x in decisions),
        "risk_gate": "blocked_missing_broker_verified_inputs",
        "broker_connected": False,
        "broker_order_adapter": "absent",
        "orders": 0,
        "execution": "disabled",
        "executable_order_intents": [],
        "realized_profit_verified": False,
    }

"""Real deterministic strategy/risk gates: no fabricated quotes, no orders."""
from copy import deepcopy
from decimal import Decimal

import pytest

from core.mojtrade_strategy_risk import (
    MAX_DAILY_LOSS, MAX_RISK_PER_TRADE, MAX_AGGREGATE_OPEN_RISK,
    MojTradeRiskError, assess_account_risk_budget, review_research,
)


@pytest.fixture
def validated_research():
    return {
        "report_type": "mojtrade-research-observation-consumption",
        "execution": "disabled", "orders": 0, "action": "research_only",
        "signals": [
            {"id": "a" * 24, "symbol": "BTC/USD", "stance": "watch_buy",
             "observed_at": "2026-11-12T17:00:00+00:00",
             "data_source": "coinbase-exchange-public-candles",
             "method": "sma20-sma50-momentum10-v1-closed-1h"},
            {"id": "b" * 24, "symbol": "ETH/USD", "stance": "neutral",
             "observed_at": "2026-11-12T17:00:00+00:00",
             "data_source": "bitstamp-public-ohlc",
             "method": "sma20-sma50-momentum10-v1-closed-1h"},
        ],
    }


def test_review_is_deterministic_and_cannot_authorize_orders(validated_research):
    a = review_research(validated_research)
    b = review_research(deepcopy(validated_research))
    assert a == b
    assert len(a["decision_digest_sha256"]) == 64
    assert a["setup_candidates_not_trades"] == 1
    assert [x["classification"] for x in a["decisions"]] == [
        "monitor_bullish", "no_setup",
    ]
    assert len(a["decisions"][0]["blockers"]) >= 5
    assert all(d["order_intent"] is None and d["execution_authorized"] is False for d in a["decisions"])
    assert a["executable_order_intents"] == []
    assert a["orders"] == 0 and a["execution"] == "disabled"
    assert not a["realized_profit_verified"]


def test_bearish_research_not_translated_into_short_order(validated_research):
    validated_research["signals"][0]["stance"] = "watch_sell"
    report = review_research(validated_research)
    assert report["decisions"][0]["classification"] == "monitor_bearish"
    assert report["decisions"][0]["order_intent"] is None
    assert report["broker_order_adapter"] == "absent"


@pytest.mark.parametrize("field,value", [
    ("orders", 1), ("execution", "demo"), ("action", "trade"),
    ("report_type", "filled_order"),
])
def test_broker_actions_cannot_be_smuggled_into_research(validated_research, field, value):
    validated_research[field] = value
    with pytest.raises(MojTradeRiskError, match="research_only_contract_required"):
        review_research(validated_research)


@pytest.mark.parametrize("change", ["signal_count", "symbol", "stance", "provenance"])
def test_research_contract_validation_rejects_malformed_inputs(validated_research, change):
    if change == "signal_count":
        validated_research["signals"].pop()
    elif change == "symbol":
        validated_research["signals"][0]["symbol"] = "XAU/USD"
    elif change == "stance":
        validated_research["signals"][0]["stance"] = "buy_now"
    else:
        validated_research["signals"][0]["data_source"] = ""
    with pytest.raises(MojTradeRiskError):
        review_research(validated_research)


def test_loss_budget_uses_account_fraction_and_existing_risk():
    r = assess_account_risk_budget(
        equity="10000.00", realized_daily_pnl="-150.00", open_stop_risk="25.00",
    )
    assert r["per_trade_risk_budget"] == "25.000000"
    assert r["daily_loss_remaining"] == "25.0000"
    assert r["portfolio_risk_remaining"] == "75.0000"
    assert r["advisory_capacity"] == "25.000000"
    assert r["risk_capacity_available"] is True
    assert r["execution_authorized"] is False
    assert r["order_quantity"] is None
    assert MAX_RISK_PER_TRADE == Decimal("0.0025")
    assert MAX_DAILY_LOSS == Decimal("0.02")
    assert MAX_AGGREGATE_OPEN_RISK == Decimal("0.01")


def test_daily_loss_limit_blocks_any_additional_capacity():
    r = assess_account_risk_budget(
        equity="10000", realized_daily_pnl="-220", open_stop_risk="0",
    )
    assert Decimal(r["daily_loss_remaining"]) == 0
    assert Decimal(r["advisory_capacity"]) == 0
    assert r["risk_capacity_available"] is False
    assert r["execution_authorized"] is False


def test_open_risk_capacity_is_exhausted_and_never_grants_trade():
    r = assess_account_risk_budget(
        equity="10000", realized_daily_pnl="50", open_stop_risk="150",
    )
    assert Decimal(r["portfolio_risk_remaining"]) == 0
    assert Decimal(r["advisory_capacity"]) == 0
    assert r["execution_authorized"] is False


@pytest.mark.parametrize(("field", "bad"), [
    ("equity", "NaN"), ("equity", "Infinity"), ("equity", "0"),
    ("equity", "-1"), ("equity", True), ("equity", 25.1),
    ("realized_daily_pnl", "nan"), ("open_stop_risk", "-1"),
    ("open_stop_risk", object()),
])
def test_unreliable_account_inputs_fail_closed(field, bad):
    data = {"equity": "1000", "realized_daily_pnl": "-10", "open_stop_risk": "2"}
    data[field] = bad
    with pytest.raises(MojTradeRiskError):
        assess_account_risk_budget(**data)

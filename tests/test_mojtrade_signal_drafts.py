"""Contract tests for private multilingual MojTrade market-watch drafts.

Synthetic signals here are unit-test inputs, not market recommendations or
performance evidence. The cards cannot contain broker orders or live signals.
"""
from datetime import datetime, timedelta, timezone
import copy
import json
import pytest

from core.mojtrade_signal_drafts import (
    MarketWatchDraftError, SCHEMA, build_market_watch_drafts,
)
from core.mojtrade_strategy_risk import MODEL_VERSION, review_research


UTC_NOW = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)
SOURCE_SHA = "c" * 64


def inputs(now=UTC_NOW):
    generated = now - timedelta(minutes=2)
    observed = now - timedelta(minutes=59)
    report = {
        "execution": "disabled",
        "orders": 0,
        "action": "research_only",
        "report_type": "mojtrade-research-observation-consumption",
        "observation_generated_at": generated.isoformat(),
        "observation_expires_at": (now + timedelta(minutes=60)).isoformat(),
        "signals": [
            {
                "id": "a" * 24, "symbol": "BTC/USD", "stance": "watch_buy",
                "observed_at": observed.isoformat(),
                "data_source": "coinbase-exchange-public-candles",
                "method": "sma20-sma50-momentum10-v1-closed-1h",
            },
            {
                "id": "b" * 24, "symbol": "ETH/USD", "stance": "neutral",
                "observed_at": observed.isoformat(),
                "data_source": "bitstamp-public-ohlc",
                "method": "sma20-sma50-momentum10-v1-closed-1h",
            },
        ],
    }
    return report, review_research(report)


def test_private_alerts_are_deterministic_source_bound_and_multilingual():
    report, review = inputs()
    first = build_market_watch_drafts(report, review, SOURCE_SHA, now=UTC_NOW)
    second = build_market_watch_drafts(report, review, SOURCE_SHA, now=UTC_NOW)
    assert first == second
    assert first["schema"] == SCHEMA
    assert first["canonical_owner"] == "mojtaba-bot-ai"
    assert first["source_sha256"] == SOURCE_SHA
    assert first["decision_sha256"] == review["decision_digest_sha256"]
    assert len(first["draft_sha256"]) == 64
    assert first["languages"] == ["fa", "en", "ar"]
    assert [x["symbol"] for x in first["alerts"]] == ["BTC/USD", "ETH/USD"]
    assert first["alerts"][0]["classification"] == "monitor_bullish"
    assert first["alerts"][1]["classification"] == "no_setup"
    for item in first["alerts"]:
        assert set(item["content"]) == {"fa", "en", "ar"}
        assert all(item["content"][lang] for lang in item["content"])
        assert item["entry_price"] is None
        assert item["stop_loss"] is None
        assert item["take_profit"] is None
        assert item["order_intent"] is None
        assert item["execution_authorized"] is False
    assert first["status"] == "private_owner_review_only"
    assert first["publication_authorized"] is False
    assert first["external_delivery_receipts"] == []
    assert first["trade_execution_authorized"] is False
    assert first["executed_orders"] == 0
    assert first["revenue_verified"] is False
    assert first["profit_verified"] is False


@pytest.mark.parametrize("change", [
    "expired", "generated_in_future", "wrong_source_id", "wrong_symbol",
    "wrong_provider", "wrong_observed", "wrong_method", "wrong_classification",
    "digest_tamper", "duplicate_ids", "enabled_execution", "broker_claim",
    "executable_intent", "bad_sha", "no_timezone",
])
def test_invalid_or_stale_signal_drafts_fail_closed(change):
    report, review = inputs()
    sha = SOURCE_SHA
    now = UTC_NOW
    if change == "expired":
        now = now + timedelta(hours=2)
    elif change == "generated_in_future":
        report["observation_generated_at"] = (now + timedelta(minutes=3)).isoformat()
    elif change == "wrong_source_id":
        review["decisions"][0]["source_signal_id"] = "e" * 24
    elif change == "wrong_symbol":
        review["decisions"][0]["symbol"] = "BTC/USDT"
    elif change == "wrong_provider":
        review["decisions"][0]["source_provider"] = "untrusted-provider"
    elif change == "wrong_observed":
        review["decisions"][0]["source_observed_at"] = now.isoformat()
    elif change == "wrong_method":
        review["decisions"][0]["source_method"] = "invalid"
    elif change == "wrong_classification":
        report["signals"][0]["stance"] = "watch_sell"
    elif change == "digest_tamper":
        review["decision_digest_sha256"] = "d" * 64
    elif change == "duplicate_ids":
        report["signals"][1]["id"] = report["signals"][0]["id"]
    elif change == "enabled_execution":
        review["execution"] = "demo"
    elif change == "broker_claim":
        review["broker_connected"] = True
    elif change == "executable_intent":
        review["executable_order_intents"] = [{"symbol": "BTC/USD"}]
    elif change == "bad_sha":
        sha = "not-sha256"
    elif change == "no_timezone":
        report["observation_expires_at"] = "2026-11-13T11:00:00"
    with pytest.raises(MarketWatchDraftError):
        build_market_watch_drafts(report, review, sha, now=now)


def test_cannot_reuse_expired_draft_as_current_market_alert():
    report, review = inputs()
    build_market_watch_drafts(report, review, SOURCE_SHA, now=UTC_NOW)
    with pytest.raises(MarketWatchDraftError, match="observation_expired_or_invalid"):
        build_market_watch_drafts(
            report, review, SOURCE_SHA, now=UTC_NOW + timedelta(days=1),
        )


def test_review_schema_must_match_current_canonical_strategy_version():
    report, review = inputs()
    assert review["schema"] == MODEL_VERSION
    review["schema"] = "unreviewed-new-strategy"
    with pytest.raises(MarketWatchDraftError, match="nonexecutable_review_required"):
        build_market_watch_drafts(report, review, SOURCE_SHA, now=UTC_NOW)

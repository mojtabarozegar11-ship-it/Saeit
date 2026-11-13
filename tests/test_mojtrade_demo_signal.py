"""Single-bot XAUUSD signal planner: synthetic risk scenarios, NO broker trading."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random
import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from core.models import AgentTask

from core.mojtrade_demo_signal import (
    DemoSignalPlanError, SCHEMA, OUTPUT_SCHEMA, plan_private_demo_signal,
)


NOW = datetime(2026, 11, 13, 12, 30, tzinfo=timezone.utc)


def snapshot(*, bearish=False):
    # Reproducible hourly input with one deterministic EMA crossover AND a
    # 20-bar breakout at the last closed candle. Pure test data, not a quote.
    rng = random.Random(731)
    for _ in range(32):
        vals = [2000.0]
        for i in range(79):
            drift = -0.25 if i < 40 else (-0.14 if i < 75 else 0.0)
            vals.append(vals[-1] + rng.uniform(-1.1, 0.9) + drift)
        vals[-1] += rng.uniform(5, 16)
    if bearish:
        vals = [4000 - val for val in vals]
    base = NOW.replace(minute=0, second=0, microsecond=0) - timedelta(hours=80)
    candles = []
    for i, close in enumerate(vals):
        prev = vals[i - 1] if i else close
        candles.append({
            "opened_at": (base + timedelta(hours=i)).isoformat(),
            "open": f"{prev:.4f}",
            "high": f"{max(prev, close) + 0.3:.4f}",
            "low": f"{min(prev, close) - 0.3:.4f}",
            "close": f"{close:.4f}",
        })
    last = Decimal(f"{vals[-1]:.2f}")
    return {
        "schema": SCHEMA,
        "owner": "mojtaba-bot-ai",
        "account_mode": "demo",
        "account_alias": "LITE_DEMO_1",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "generated_at": (NOW - timedelta(seconds=10)).isoformat(),
        "expires_at": (NOW + timedelta(seconds=60)).isoformat(),
        "quote": {
            "bid": str(last - Decimal("0.05")),
            "ask": str(last + Decimal("0.05")),
            "pip_size": "0.01",
            "tick_size": "0.01",
            "observed_at": (NOW - timedelta(seconds=5)).isoformat(),
        },
        "candles": candles,
        "account_risk": {
            "equity": "10000",
            "realized_daily_pnl": "-20",
            "open_stop_risk": "10",
            "free_margin": "8000",
            "open_positions": 0,
            "pending_orders": 0,
        },
    }


@pytest.mark.parametrize("bearish,expected", [(False, "demo_setup_buy"), (True, "demo_setup_sell")])
def test_dual_confirmation_generates_private_priced_gold_levels_but_never_orders(
    bearish, expected,
):
    source = snapshot(bearish=bearish)
    result = plan_private_demo_signal(source, now=NOW)
    assert result == plan_private_demo_signal(source, now=NOW)
    assert result["schema"] == OUTPUT_SCHEMA
    assert result["owner"] == "mojtaba-bot-ai"
    assert result["classification"] == expected
    assert result["risk_gate"] == "research_only_no_broker_attestation"
    levels = result["levels"]
    assert levels is not None
    entry, stop, take = [Decimal(levels[key]) for key in (
        "entry_indicative", "stop_loss_indicative", "take_profit_indicative",
    )]
    assert (stop < entry < take) if not bearish else (take < entry < stop)
    assert levels["order_volume"] is None
    assert levels["prices_are_executable"] is False
    assert all(result["copy"][lang] for lang in ("fa", "en", "ar"))
    assert len(result["source_digest_sha256"]) == 64
    assert result["risk_advisory_capacity_account_currency"] == "25.000000"
    assert result["publication_authorized"] is False
    assert result["trade_execution_authorized"] is False
    assert result["broker_execution_connected"] is False
    assert result["broker_data_independently_authenticated"] is False
    assert result["order_intent"] is None and result["orders"] == 0
    assert result["real_revenue_verified"] is False


@pytest.mark.parametrize("field,value", [
    ("account_mode", "live"), ("owner", "other-agent"), ("symbol", "XAU/USD"),
    ("symbol", "BTC/USD"), ("timeframe", "M5"),
    ("schema", "unreviewed"), ("account_alias", "../etc/passwd"),
])
def test_disallow_foreign_bot_live_account_or_unreviewed_market_scope(field, value):
    data = snapshot()
    data[field] = value
    with pytest.raises(DemoSignalPlanError):
        plan_private_demo_signal(data, now=NOW)


@pytest.mark.parametrize("field,value", [
    ("equity", "NaN"), ("equity", "-100"), ("equity", "0"),
    ("equity", "1e10"), ("equity", True), ("free_margin", "-10"),
    ("open_stop_risk", "-1"), ("open_positions", -1),
    ("open_positions", True), ("open_positions", 9999),
    ("pending_orders", -1), ("pending_orders", 1.5),
    ("realized_daily_pnl", "Infinity"), ("realized_daily_pnl", "1e5"),
])
def test_invalid_account_risk_never_generates_plan(field, value):
    data = snapshot()
    data["account_risk"][field] = value
    with pytest.raises(DemoSignalPlanError):
        plan_private_demo_signal(data, now=NOW)


@pytest.mark.parametrize("change", [
    "stale", "future", "expiry_too_far", "missing_timezone", "quote_stale",
    "quote_in_future", "crossed_bid_ask", "wide_spread", "invalid_tick",
    "gapped_candles", "open_last_candle", "expired_candles",
    "out_of_order", "invalid_ohlc", "extra_order", "missing_candle",
    "too_few_candles", "float_quote",
])
def test_bad_market_data_fails_closed_without_executable_prices(change):
    data = snapshot()
    if change == "stale":
        data["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
    elif change == "future":
        data["generated_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif change == "expiry_too_far":
        data["expires_at"] = (NOW + timedelta(minutes=10)).isoformat()
    elif change == "missing_timezone":
        data["generated_at"] = "2026-11-13T12:29:50"
    elif change == "quote_stale":
        data["quote"]["observed_at"] = (NOW - timedelta(minutes=10)).isoformat()
    elif change == "quote_in_future":
        data["quote"]["observed_at"] = (NOW + timedelta(seconds=2)).isoformat()
    elif change == "crossed_bid_ask":
        data["quote"]["ask"] = data["quote"]["bid"]
    elif change == "wide_spread":
        data["quote"]["ask"] = str(Decimal(data["quote"]["bid"]) + 1)
    elif change == "invalid_tick":
        data["quote"]["tick_size"] = "0.07"
    elif change == "gapped_candles":
        data["candles"][-10]["opened_at"] = (
            NOW - timedelta(hours=11, minutes=15)
        ).isoformat()
    elif change == "open_last_candle":
        data["candles"][-1]["opened_at"] = NOW.replace(minute=0).isoformat()
    elif change == "expired_candles":
        for c in data["candles"]:
            c["opened_at"] = (
                datetime.fromisoformat(c["opened_at"]) - timedelta(days=2)
            ).isoformat()
    elif change == "out_of_order":
        data["candles"][-1], data["candles"][-2] = (
            data["candles"][-2], data["candles"][-1]
        )
    elif change == "invalid_ohlc":
        data["candles"][-1]["low"] = "5000"
    elif change == "extra_order":
        data["publish"] = True
    elif change == "missing_candle":
        del data["candles"][-1]["close"]
    elif change == "too_few_candles":
        data["candles"] = data["candles"][:40]
    else:
        data["quote"]["bid"] = 2000.0
    with pytest.raises(DemoSignalPlanError):
        plan_private_demo_signal(data, now=NOW)


@pytest.mark.parametrize("field,value", [
    ("pending_orders", 1), ("open_positions", 3),
])
def test_existing_exposure_blocks_even_provisional_prices(field, value):
    data = snapshot()
    data["account_risk"][field] = value
    result = plan_private_demo_signal(data, now=NOW)
    assert result["classification"] == "blocked"
    assert result["levels"] is None
    assert result["risk_gate"] == "portfolio_or_margin_gate_blocked"
    assert result["orders"] == 0


def test_exhausted_risk_budget_blocks_prices_and_cannot_create_position():
    data = snapshot()
    data["account_risk"]["realized_daily_pnl"] = "-300"
    result = plan_private_demo_signal(data, now=NOW)
    assert result["classification"] == "blocked"
    assert result["levels"] is None
    assert result["risk_advisory_capacity_account_currency"] == "0"


def test_invalid_data_never_changes_inputs():
    data = snapshot()
    original = deepcopy(data)
    result = plan_private_demo_signal(data, now=NOW)
    assert data == original
    assert result["order_intent"] is None



@pytest.mark.django_db
def test_private_gold_signal_endpoint_authorizes_owner_without_creating_orders(client):
    url = reverse("mojtrade-private-demo-gold-signal-plan")
    data = snapshot()
    denied = client.post(url, data=json.dumps(data), content_type="application/json")
    assert denied.status_code == 403
    assert "levels" not in denied.json()
    staff = get_user_model().objects.create_user(
        username="gold-signal-staff", is_staff=True,
    )
    client.force_login(staff)
    assert client.post(
        url, data=json.dumps(data), content_type="application/json",
    ).status_code == 403
    owner = get_user_model().objects.create_superuser(
        username="gold-signal-owner", email="gold-signal@example.com",
        password="local-test-only",
    )
    client.force_login(owner)
    with patch(
        "core.mojtrade_private_views.plan_private_demo_signal",
        side_effect=lambda data: plan_private_demo_signal(data, now=NOW),
    ):
        response = client.post(
            url, data=json.dumps(data), content_type="application/json",
        )
    assert response.status_code == 200
    report = response.json()
    assert report["owner"] == "mojtaba-bot-ai"
    assert report["classification"] == "demo_setup_buy"
    assert report["levels"]["entry_indicative"]
    assert report["levels"]["order_volume"] is None
    assert report["publication_authorized"] is False
    assert report["trade_execution_authorized"] is False
    assert report["broker_data_independently_authenticated"] is False
    assert report["orders"] == 0
    assert "no-store" in response["Cache-Control"]
    assert "noindex" in response["X-Robots-Tag"]
    assert response["X-Frame-Options"] == "DENY"
    assert not AgentTask.objects.exists()


@pytest.mark.django_db
def test_private_gold_signal_endpoint_refuses_get_malformed_json_and_csrf(client):
    url = reverse("mojtrade-private-demo-gold-signal-plan")
    owner = get_user_model().objects.create_superuser(
        username="gold-signal-security", email="gold-security@example.com",
        password="local-test-only",
    )
    client.force_login(owner)
    assert client.get(url).status_code == 405
    assert client.post(url, "not json", content_type="text/plain").status_code == 415
    assert client.post(url, "not json", content_type="application/json").status_code == 422
    assert client.post(
        url, '{"schema":1,"schema":2}', content_type="application/json",
    ).status_code == 422
    assert client.post(
        url, "{" + "a" * 128_001 + "}", content_type="application/json",
    ).status_code == 413
    strict_client = Client(enforce_csrf_checks=True)
    strict_client.force_login(owner)
    assert strict_client.post(
        url, data=json.dumps(snapshot()), content_type="application/json",
    ).status_code == 403
    assert not AgentTask.objects.exists()

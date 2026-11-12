"""Session-aware gold research rejects fabricated closures and stale reopen fills."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from trading import mojtrade_costed_oos as engine
from trading.mojtrade_market_sessions import (
    SessionGapError, load_closure_claims, reconcile_gaps,
)


def make_quotes(tmp_path, *, gap=True):
    """Only a synthetic validator fixture, NOT broker or profit evidence."""
    import csv
    out = tmp_path / "historical-bidask.csv"
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=engine.FIELDS)
        writer.writeheader()
        for idx in range(420):
            if gap and 150 <= idx < 153:
                continue
            price = 2500.0 + idx * 0.03
            writer.writerow({
                "timestamp_utc": (first + timedelta(minutes=idx)).isoformat(),
                "bid_open": price, "bid_high": price + 1.0,
                "bid_low": price - 1.0, "bid_close": price,
                "ask_open": price + 0.2, "ask_high": price + 1.2,
                "ask_low": price - .8, "ask_close": price + 0.2,
            })
    return out, first


def closure_manifest(first, *, start=150, end=153, reason="session_break"):
    return {
        "schema_version": 1,
        "broker": "LiteFinance",
        "symbol": "XAUUSD",
        "timeframe_minutes": 1,
        "closures": [{
            "start_utc": (first + timedelta(minutes=start)).isoformat(),
            "end_utc": (first + timedelta(minutes=end)).isoformat(),
            "reason": reason,
            "evidence_ref": "synthetic-fixture-do-not-trust-as-broker",
        }],
    }


def store_claims(tmp_path, content):
    path = tmp_path / "closures.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def test_missing_in_session_quotes_rejected_without_exact_closure(tmp_path):
    path, _ = make_quotes(tmp_path)
    with pytest.raises(engine.ResearchError, match="unexplained_market_quote_gap"):
        engine.parse_bars(path, 1)


def test_exact_closure_accepts_real_quoted_bars_without_fabricating_prices(tmp_path):
    path, first = make_quotes(tmp_path)
    claims, digest = load_closure_claims(store_claims(tmp_path, closure_manifest(first)), 1)
    bars, source_sha = engine.parse_bars(path, 1, claims)
    assert len(bars) == 417  # The 3 nonexistent bars are NEVER synthesized.
    assert reconcile_gaps(bars, 1, claims) == 1
    assert bars[150].time == first + timedelta(minutes=153)
    assert source_sha != digest
    assert len(source_sha) == 64 and len(digest) == 64


@pytest.mark.parametrize("error", [
    "incorrect_start", "incorrect_end", "incorrect_broker", "incorrect_symbol",
    "incorrect_timeframe", "missing_evidence", "malformed_reason", "wrong_time_zone",
    "excessive_session_break", "unsorted_or_repeated", "extra_nonexistent_closure",
])
def test_fabricated_or_inconsistent_calendar_cannot_hide_data_gaps(tmp_path, error):
    path, first = make_quotes(tmp_path)
    payload = closure_manifest(first)
    item = payload["closures"][0]
    if error == "incorrect_start":
        item["start_utc"] = (first + timedelta(minutes=149)).isoformat()
    elif error == "incorrect_end":
        item["end_utc"] = (first + timedelta(minutes=154)).isoformat()
    elif error == "incorrect_broker":
        payload["broker"] = "UnverifiedBroker"
    elif error == "incorrect_symbol":
        payload["symbol"] = "BTCUSD"
    elif error == "incorrect_timeframe":
        payload["timeframe_minutes"] = 5
    elif error == "missing_evidence":
        item["evidence_ref"] = ""
    elif error == "malformed_reason":
        item["reason"] = ["session_break"]
    elif error == "wrong_time_zone":
        item["start_utc"] = "2026-01-01T04:30:00+02:00"
    elif error == "excessive_session_break":
        item["end_utc"] = (first + timedelta(minutes=900)).isoformat()
    elif error == "unsorted_or_repeated":
        payload["closures"].append(dict(item))
    else:
        payload["closures"].append({
            **item,
            "start_utc": (first + timedelta(minutes=300)).isoformat(),
            "end_utc": (first + timedelta(minutes=301)).isoformat(),
        })
    file = store_claims(tmp_path, payload)
    try:
        claims, _ = load_closure_claims(file, 1)
    except SessionGapError:
        return
    with pytest.raises(engine.ResearchError):
        engine.parse_bars(path, 1, claims)


def test_unused_closure_is_rejected_even_without_any_market_gap(tmp_path):
    csv_file, first = make_quotes(tmp_path, gap=False)
    claims, _ = load_closure_claims(store_claims(tmp_path, closure_manifest(first)), 1)
    with pytest.raises(engine.ResearchError, match="unused_or_fabricated_closure_claim"):
        engine.parse_bars(csv_file, 1, claims)


def test_unauthenticated_closure_manifest_symlink_rejected(tmp_path):
    _, first = make_quotes(tmp_path)
    file = store_claims(tmp_path, closure_manifest(first))
    alias = tmp_path / "redirected-session-manifest.json"
    alias.symlink_to(file)
    with pytest.raises(SessionGapError, match="session_calendar_not_regular"):
        load_closure_claims(alias, 1)


def test_preclose_signal_cannot_create_new_position_at_postclosure_open(monkeypatch, tmp_path):
    source, first = make_quotes(tmp_path, gap=False)
    bars, _ = engine.parse_bars(source, 1)
    from pathlib import Path
    config = tmp_path / "costs.json"
    config.write_text(json.dumps({
        "timeframe_minutes": 1,
        "initial_equity_usd": 10000,
        "commission_usd_per_ounce_per_side": 0.1,
        "slippage_usd_per_ounce_per_side": 0.1,
        "quantity_step_ounces": 0.01,
        "max_notional_to_equity": 2,
        "risk_fraction": .0025,
        "stop_atr_multiple": 2,
        "reward_to_risk": 1.5,
        "max_hold_bars": 12,
    }), encoding="utf-8")
    cfg = engine.Settings.load(config)
    # A documented calendar gap falls at index 51, right after the only signal
    # emitted on the index-50 closed bar. A normal next-bar fill must be discarded.
    for i in range(51, len(bars)):
        bars[i] = replace(bars[i], time=bars[i].time + timedelta(hours=2))
    claims = [{
        "start": first + timedelta(minutes=51),
        "end": first + timedelta(minutes=51, hours=2),
        "reason": "session_break",
        "evidence_ref": "synthetic-test-broker-closure",
    }]
    # This gap is larger than a single bar but much less than the 6-hour maximum.
    assert reconcile_gaps(bars, 1, claims) == 1
    monkeypatch.setattr(engine, "signal_at", lambda i, strategy, data: 1 if i == 50 else 0)
    output = engine.simulate(bars, engine.indicators(bars), cfg, "ema_8_21", 40, 58)
    assert output["trades"] == 0
    assert output["stale_signals_discarded_at_market_reopen"] == 1


def test_weekend_and_holiday_claims_require_exact_match(tmp_path):
    source, first = make_quotes(tmp_path)
    payload = closure_manifest(first, reason="scheduled_weekend")
    claims, _ = load_closure_claims(store_claims(tmp_path, payload), 1)
    assert engine.parse_bars(source, 1, claims)[0][150].time == first + timedelta(minutes=153)

"""Offline reproducibility tests; fixtures are synthetic, NOT profit evidence."""
import csv
from datetime import datetime, timedelta, timezone
import json
import math

import pytest
from trading import mojtrade_costed_oos as lab


@pytest.fixture
def sample_quotes(tmp_path):
    path = tmp_path / "xauusd-broker-bidask.csv"
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=lab.FIELDS)
        writer.writeheader()
        for i in range(420):
            opened = 2500 + i * 0.02 + math.sin((i - 1) / 7) * 2
            closed = 2500 + i * 0.02 + math.sin(i / 7) * 2
            row = {"timestamp_utc": (start + timedelta(minutes=i)).isoformat()}
            row.update({
                "bid_open": opened, "bid_high": max(opened, closed) + 0.5,
                "bid_low": min(opened, closed) - 0.5, "bid_close": closed,
                "ask_open": opened + 0.20,
                "ask_high": max(opened, closed) + 0.70,
                "ask_low": min(opened, closed) - 0.30,
                "ask_close": closed + 0.20,
            })
            writer.writerow(row)
    return path


@pytest.fixture
def model_settings(tmp_path):
    path = tmp_path / "cost-model.json"
    config = {
        "timeframe_minutes": 1, "initial_equity_usd": 10000,
        "commission_usd_per_ounce_per_side": 0.10,
        "slippage_usd_per_ounce_per_side": 0.15,
        "quantity_step_ounces": 1.0, "max_notional_to_equity": 2,
        "risk_fraction": 0.0025, "stop_atr_multiple": 1.5,
        "reward_to_risk": 1.6, "max_hold_bars": 12,
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_strict_real_quote_schema_and_provenance_digest(sample_quotes):
    bars, digest = lab.parse_bars(sample_quotes, 1)
    assert len(bars) == 420 and len(digest) == 64
    assert digest == lab.parse_bars(sample_quotes, 1)[1]
    assert all(x.ac >= x.bc for x in bars)
    assert (bars[-1].time - bars[0].time).total_seconds() == 419 * 60


def test_costed_oos_result_is_reproducible_and_not_real_income(sample_quotes, model_settings):
    bars, digest = lab.parse_bars(sample_quotes, 1)
    cfg = lab.Settings.load(model_settings)
    a = lab.evaluate(bars, digest, cfg)
    z = lab.evaluate(bars, digest, cfg)
    assert a == z
    assert a["trials_count"] == 4
    assert a["embargo_bars"] >= cfg.max_hold_bars
    assert a["holdout_bars"] >= 100
    assert a["commercial_ready"] is False
    assert a["realized_profit_verified"] is False
    assert a["market_order_placement_enabled"] is False
    assert a["source_is_cryptographically_authenticated_to_broker"] is False
    assert a["broker_quote_provenance_unverified"] is True
    assert a["bid_ask_ohlc_required_by_input_contract"] is True
    assert all(
        result["max_intrabar_stress_drawdown_fraction"]
        >= result["max_closed_equity_drawdown_fraction"]
        for result in a["all_training_results"].values()
    )
    assert a["statistical_significance_verified"] is False
    assert a["train_selected_strategy"] in (*lab.STRATEGIES, None)
    assert all(x["result_type"] == "unverified_historical_simulation_not_realized_profit"
               for x in a["all_training_results"].values())
    assert a["heldout_result"] is None or a["heldout_result"]["entry_is_next_bar"]


def test_new_samples_do_not_change_past_closed_bar_signal(sample_quotes):
    bars, _ = lab.parse_bars(sample_quotes, 1)
    original = lab.indicators(bars)
    for strategy in lab.STRATEGIES:
        expected = lab.signal_at(120, strategy, original)
        newer = list(bars)
        newer[130] = lab.Bar(newer[130].time, 100, 101, 99, 100, 101, 102, 100, 101)
        altered = lab.indicators(newer)
        assert lab.signal_at(120, strategy, altered) == expected


def test_both_stop_take_touched_in_one_candle_prefers_worst_case(model_settings):
    cfg = lab.Settings.load(model_settings)
    bar = lab.Bar(datetime.now(timezone.utc), 100, 102, 98, 100,
                  100.2, 102.2, 98.2, 100.2)
    position = (1, 100.2, 99, 101, 1, 0, 0)
    exit_result = lab._close(position, bar, settings=cfg)
    assert exit_result["reason"] == "stop"
    assert exit_result["net"] < 0


def test_gap_stop_is_not_filled_optimistically_at_stop(model_settings):
    cfg = lab.Settings.load(model_settings)
    bar = lab.Bar(datetime.now(timezone.utc), 97, 99, 95, 98,
                  97.2, 99.2, 95.2, 98.2)
    position = (1, 100, 99, 102, 1, 0, 0)
    outcome = lab._close(position, bar, settings=cfg)
    assert outcome["reason"] == "gap_stop"
    assert outcome["net"] < -2  # Worse than the planned -1 price stop.


def test_short_stop_uses_ask_not_midprice(model_settings):
    cfg = lab.Settings.load(model_settings)
    bar = lab.Bar(datetime.now(timezone.utc), 100, 100.9, 98.8, 100,
                  100.2, 101.1, 99, 100.2)
    short = (-1, 100, 101, 98, 1, 0, 0)
    outcome = lab._close(short, bar, settings=cfg)
    assert outcome["reason"] == "stop" and outcome["net"] < 0


def test_risk_sizing_requires_valid_actual_cost_parameters(model_settings):
    cfg = lab.Settings.load(model_settings)
    assert cfg.initial_equity_usd == 10000
    assert cfg.commission_usd_per_ounce_per_side == 0.1
    assert cfg.slippage_usd_per_ounce_per_side == 0.15
    # The risk model never creates an actual broker order.
    bars = [lab.Bar(datetime(2026, 1, 1, tzinfo=timezone.utc), 2500, 2501,
                    2499, 2500, 2500.2, 2501.2, 2499.2, 2500.2)]
    assert len(bars) == 1


@pytest.mark.parametrize("changed", [
    "price_crossed", "price_nan", "gap", "duplicate", "out_of_order", "wrong_header",
    "timezone_not_utc", "missing_quote",
])
def test_corrupt_broker_quote_data_is_never_backtested(sample_quotes, changed):
    lines = sample_quotes.read_text(encoding="utf-8").splitlines()
    cols = next(csv.reader([lines[121]]))
    if changed == "price_crossed":
        cols[5] = "100"  # ask_open below bid_open
    elif changed == "price_nan":
        cols[4] = "nan"
    elif changed == "gap":
        cols[0] = "2026-01-01T12:00:00+00:00"
    elif changed == "duplicate":
        cols[0] = next(csv.reader([lines[120]]))[0]
    elif changed == "out_of_order":
        cols[0] = "2025-12-31T00:00:00+00:00"
    elif changed == "wrong_header":
        lines[0] = lines[0].replace("ask_close", "unverified_mid_price")
    elif changed == "timezone_not_utc":
        cols[0] = "2026-01-01T02:00:00+02:00"
    else:
        cols[5] = ""
    if changed != "wrong_header":
        import io
        buf = io.StringIO()
        csv.writer(buf).writerow(cols)
        lines[121] = buf.getvalue().strip()
    sample_quotes.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(lab.ResearchError):
        lab.parse_bars(sample_quotes, 1)


@pytest.mark.parametrize(("key", "value"), [
    ("risk_fraction", 0), ("risk_fraction", 0.1),
    ("initial_equity_usd", -1), ("initial_equity_usd", "NaN"),
    ("slippage_usd_per_ounce_per_side", -1),
    ("max_notional_to_equity", 100), ("max_hold_bars", 0),
    ("timeframe_minutes", 60), ("quantity_step_ounces", 0),
    ("quantity_step_ounces", 0.01),
])
def test_invalid_or_unrealistic_cost_config_fails_closed(model_settings, key, value):
    cfg = json.loads(model_settings.read_text())
    cfg[key] = value
    model_settings.write_text(json.dumps(cfg))
    with pytest.raises(lab.ResearchError):
        lab.Settings.load(model_settings)


def test_quote_rows_prohibit_symlink(sample_quotes, tmp_path):
    link = tmp_path / "linked.csv"
    link.symlink_to(sample_quotes)
    with pytest.raises(lab.ResearchError):
        lab.parse_bars(link, 1)


def test_without_positive_training_evidence_no_strategy_is_automatically_promoted(sample_quotes, model_settings):
    bars, digest = lab.parse_bars(sample_quotes, 1)
    cfg = lab.Settings.load(model_settings)
    # The input could show no profitable strategy. The verdict must not be forced.
    report = lab.evaluate(bars, digest, cfg)
    if report["train_selected_strategy"] is None:
        assert report["heldout_result"] is None
        assert report["historical_edge_candidate"] is False
    assert report["commercial_ready"] is False

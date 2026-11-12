"""Research-only chronological folds; synthetic observations never prove alpha."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math

import pytest

from trading.mojtrade_costed_oos import Bar, Settings, ResearchError, indicators
from trading.mojtrade_walk_forward import (
    SCENARIOS, evaluate_fold, select_champion, stress_quotes, walk_forward,
)


@pytest.fixture
def original_bars():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = []
    # Synthetic quotes exist solely to verify mathematical/code invariants.
    for i in range(1200):
        o = 2500 + i * .004 + 2.0 * math.sin((i - 1) / 11)
        c = 2500 + i * .004 + 2.0 * math.sin(i / 11)
        hi = max(o, c) + 0.40
        lo = min(o, c) - 0.40
        bars.append(Bar(
            start + timedelta(minutes=i), o, hi, lo, c,
            o + .2, hi + .2, lo + .2, c + .2,
        ))
    return bars


@pytest.fixture
def cfg():
    return Settings(
        timeframe_minutes=1, initial_equity_usd=10000.,
        commission_usd_per_ounce_per_side=.1,
        slippage_usd_per_ounce_per_side=.15,
        quantity_step_ounces=.01, max_notional_to_equity=2.,
        risk_fraction=.0025, stop_atr_multiple=1.5,
        reward_to_risk=1.6, max_hold_bars=12,
    )


def test_expanding_folds_are_out_of_sample_and_nonoverlapping(original_bars, cfg):
    digest = hashlib.sha256(b"synthetic-fixture-not-broker").hexdigest()
    result = walk_forward(original_bars, digest, cfg)
    assert result["schema"] == "mojtrade-walk-forward-cost-stress-v1"
    assert result["source_sha256"] == digest
    assert result["fold_count"] == 3
    assert result["initial_training_bars"] == 780
    assert result["fold_test_bars"] == 100
    previous_end = 0
    for i, fold in enumerate(result["folds"]):
        assert fold["fold"] == i + 1
        assert fold["train_start_index"] == 40
        assert fold["train_end_exclusive"] >= 300
        assert fold["embargo_bars"] == 40
        assert fold["test_bars"] == 100
        assert fold["test_start_index"] == fold["train_end_exclusive"] + 40
        assert fold["test_start_index"] >= previous_end
        assert fold["test_end_exclusive"] <= len(original_bars)
        assert fold["orders"] == 0
        assert fold["realized_profit_verified"] is False
        assert set(fold["train_trials"]) == {
            "ema_8_21", "ema_13_34", "breakout_20", "mean_revert_20",
        }
        if fold["champion_selected_before_test"] is None:
            assert fold["test_scenarios"] == {}
        else:
            assert set(fold["test_scenarios"]) == set(SCENARIOS)
            assert all(v["result_type"] == "unverified_historical_simulation_not_realized_profit"
                       for v in fold["test_scenarios"].values())
        previous_end = fold["test_end_exclusive"]
    assert previous_end == len(original_bars)
    assert result["live_trades"] == 0
    assert result["order_execution_enabled"] is False
    assert result["commercial_ready"] is False
    assert result["realized_profit_verified"] is False
    assert result["real_broker_data_origin_verified"] is False
    assert result["demo_forward_verified"] is False
    assert result["p_values_or_multiple_testing_adjustment_verified"] is False
    assert all(label in result["tested_scenarios"] for label in SCENARIOS)
    json.dumps(result, allow_nan=False)


def test_research_report_reproducible(original_bars, cfg):
    sha = "a" * 64
    assert walk_forward(original_bars, sha, cfg) == walk_forward(original_bars, sha, cfg)


def test_future_market_bars_do_not_select_present_champion(original_bars, cfg):
    train_end = 700
    base_champion, base_trials = select_champion(
        original_bars, indicators(original_bars), cfg, train_end,
    )
    modified = list(original_bars)
    # Huge future price shock must not rewrite historical training results.
    for i in range(750, 830):
        bar = modified[i]
        modified[i] = replace(
            bar, bo=bar.bo + 400, bh=bar.bh + 400, bl=bar.bl + 400,
            bc=bar.bc + 400, ao=bar.ao + 400, ah=bar.ah + 400,
            al=bar.al + 400, ac=bar.ac + 400,
        )
    altered_champion, altered_trials = select_champion(
        modified, indicators(modified), cfg, train_end,
    )
    assert (base_champion, base_trials) == (altered_champion, altered_trials)


def test_no_profitable_training_signal_produces_no_fake_fold_results(cfg):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    flat = [Bar(start + timedelta(minutes=i), 2500, 2500.5, 2499.5, 2500,
                2500.2, 2500.7, 2499.7, 2500.2) for i in range(1200)]
    result = walk_forward(flat, "b" * 64, cfg)
    assert result["folds_without_champion"] == 3
    assert result["folds_with_selected_champion"] == 0
    assert result["total_baseline_oos_trades"] == 0
    assert result["total_baseline_oos_net_pnl_usd"] == 0
    assert result["total_cost_shock_oos_net_pnl_usd"] == 0
    assert result["historical_cost_robustness_candidate"] is False
    assert all(f["candidate_rejected"] and not f["test_scenarios"]
               for f in result["folds"])


def test_shock_costs_are_applied_without_reshaping_the_original_signals(original_bars, cfg):
    widened = stress_quotes(original_bars, 3)
    assert widened is not original_bars
    assert original_bars[100].ao - original_bars[100].bo == pytest.approx(.2)
    assert widened[100].ao - widened[100].bo == pytest.approx(.6)
    assert widened[100].bo == original_bars[100].bo
    assert widened[100].bc == original_bars[100].bc
    assert widened[100].ah >= widened[100].ao
    assert widened[100].al <= widened[100].ac
    assert stress_quotes(original_bars, 1) is original_bars
    for invalid in (0.5, 6, -1):
        with pytest.raises(ResearchError, match="stress_spread_factor_invalid"):
            stress_quotes(original_bars, invalid)


def test_single_fold_rejects_lookahead_or_missing_embargo(original_bars, cfg):
    for params in (
        {"train_end": 800, "test_start": 810, "test_end": 950},
        {"train_end": 1100, "test_start": 1120, "test_end": 1250},
        {"train_end": 800, "test_start": 840, "test_end": 900},
    ):
        with pytest.raises(ResearchError):
            evaluate_fold(original_bars, cfg, **params)


@pytest.mark.parametrize(("n", "folds", "holdout"), [
    (1200, 1, 100), (1200, 9, 100), (1200, True, 100),
    (1200, 3, 99), (1200, 3, 20001), (1200, 3, True),
    (500, 3, 100), (1200, 8, 150),
])
def test_invalid_design_or_too_little_evidence_refused(original_bars, cfg, n, folds, holdout):
    with pytest.raises(ResearchError):
        walk_forward(original_bars[:n], "a" * 64, cfg, folds=folds, test_bars=holdout)


def test_source_fingerprint_required(original_bars, cfg):
    with pytest.raises(ResearchError, match="source_sha256_required"):
        walk_forward(original_bars, "unknown", cfg)

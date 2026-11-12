"""Chronological multi-fold MojTrade model selection and execution-cost stress.

This is a research engine only. It cannot place orders, access broker accounts
or prove realized P&L. It uses the existing bid/ask simulation and source hash.
Every strategy is chosen using past training data; each later fold is unseen
at the moment its strategy is chosen. Trials and rejected folds are retained.
"""
from __future__ import annotations

from dataclasses import replace

from trading.mojtrade_costed_oos import (
    MIN_BARS, STRATEGIES, ResearchError, indicators, simulate,
)


MODEL = "mojtrade-walk-forward-cost-stress-v1"
# Multipliers act on the same observed bid/ask bars, without inventing new prices.
SCENARIOS = {
    "broker_assumptions": (1.0, 1.0, 1.0),
    "wider_market": (1.5, 1.5, 1.5),
    "severe_cost_shock": (3.0, 3.0, 2.0),
}


def stress_quotes(bars, spread_multiplier):
    """Shift the ask quote, preserving each field's original bid/ask spread."""
    if not 1 <= spread_multiplier <= 5:
        raise ResearchError("stress_spread_factor_invalid")
    if spread_multiplier == 1:
        return bars
    adjusted = []
    for bar in bars:
        adjusted.append(replace(
            bar,
            ao=bar.bo + spread_multiplier * (bar.ao - bar.bo),
            ah=bar.bh + spread_multiplier * (bar.ah - bar.bh),
            al=bar.bl + spread_multiplier * (bar.al - bar.bl),
            ac=bar.bc + spread_multiplier * (bar.ac - bar.bc),
        ))
    return adjusted


def select_champion(bars, data, cfg, train_end):
    """Select only with observations strictly before the upcoming embargo."""
    if train_end < MIN_BARS:
        raise ResearchError("walk_forward_insufficient_training")
    trials = {
        name: simulate(bars, data, cfg, name, 40, train_end)
        for name in STRATEGIES
    }
    eligible = [
        (name, score) for name, score in trials.items()
        if score["trades"] >= 5 and score["net_pnl_usd"] > 0
        and score["max_closed_equity_drawdown_fraction"] < 0.25
    ]
    champion = max(eligible, key=lambda item: (item[1]["net_pnl_usd"], item[0]))[0] if eligible else None
    return champion, trials


def evaluate_fold(
    bars, cfg, *, train_end, test_start, test_end,
    baseline_indicators=None,
):
    """Never train on embargo or test bars, and never rank by test results."""
    if not (MIN_BARS <= train_end < test_start < test_end <= len(bars)):
        raise ResearchError("walk_forward_invalid_split")
    if test_start - train_end < max(40, cfg.max_hold_bars):
        raise ResearchError("walk_forward_embargo_too_short")
    if test_end - test_start < 100:
        raise ResearchError("walk_forward_holdout_too_short")
    data = baseline_indicators if baseline_indicators is not None else indicators(bars)
    champion, trials = select_champion(bars, data, cfg, train_end)
    tested = {}
    if champion is not None:
        for label, (spread_mult, slip_mult, fee_mult) in SCENARIOS.items():
            scenario_cfg = replace(
                cfg,
                slippage_usd_per_ounce_per_side=cfg.slippage_usd_per_ounce_per_side * slip_mult,
                commission_usd_per_ounce_per_side=cfg.commission_usd_per_ounce_per_side * fee_mult,
            )
            tested[label] = simulate(
                stress_quotes(bars, spread_mult),
                data, scenario_cfg, champion, test_start, test_end,
            )
    return {
        "train_start_index": 40,
        "train_end_exclusive": train_end,
        "embargo_start_index": train_end,
        "test_start_index": test_start,
        "test_end_exclusive": test_end,
        "train_bars": train_end - 40,
        "embargo_bars": test_start - train_end,
        "test_bars": test_end - test_start,
        "train_trials": trials,
        "champion_selected_before_test": champion,
        "test_scenarios": tested,
        "candidate_rejected": champion is None,
        "orders": 0,
        "realized_profit_verified": False,
    }


def walk_forward(bars, source_sha256, cfg, *, folds=3, test_bars=100):
    """Expanding past-only training with nonoverlapping future holdout windows.

    Each test fold follows a distinct embargo. Previous folds become available
    as training observations for later folds, just as in actual time.
    Test results never select the champion within that same fold.
    """
    if type(folds) is not int or not 2 <= folds <= 8:
        raise ResearchError("walk_forward_folds_out_of_bounds")
    if type(test_bars) is not int or not 100 <= test_bars <= 20_000:
        raise ResearchError("walk_forward_test_bars_out_of_bounds")
    if not isinstance(source_sha256, str) or len(source_sha256) != 64:
        raise ResearchError("source_sha256_required")
    embargo = max(40, cfg.max_hold_bars)
    initial_train_end = len(bars) - folds * (test_bars + embargo)
    if initial_train_end < MIN_BARS:
        raise ResearchError("walk_forward_more_real_bars_required")

    data = indicators(bars)
    fold_results = []
    for index in range(folds):
        training_end = initial_train_end + index * (test_bars + embargo)
        start = training_end + embargo
        end = start + test_bars
        result = evaluate_fold(
            bars, cfg,
            train_end=training_end, test_start=start, test_end=end,
            baseline_indicators=data,
        )
        fold_results.append({"fold": index + 1, **result})

    selected = [fold for fold in fold_results if not fold["candidate_rejected"]]
    all_selected = len(selected) == folds
    baseline = [fold["test_scenarios"]["broker_assumptions"] for fold in selected]
    shock = [fold["test_scenarios"]["severe_cost_shock"] for fold in selected]
    # A non-promotional label only. No p-values, multiple-testing correction,
    # verified upstream broker origin, or forward demo have been established.
    indicative = bool(
        all_selected
        and all(r["trades"] >= 5 and r["net_pnl_usd"] > 0
                and r["profit_factor"] is not None and r["profit_factor"] > 1.1
                and r["max_intrabar_stress_drawdown_fraction"] < 0.15 for r in baseline)
        and all(r["trades"] >= 5 and r["net_pnl_usd"] > 0 for r in shock)
    )
    return {
        "schema": MODEL,
        "symbol": "XAUUSD",
        "source_sha256": source_sha256,
        "timeframe_minutes": cfg.timeframe_minutes,
        "fold_count": folds,
        "fold_test_bars": test_bars,
        "embargo_bars_per_fold": embargo,
        "initial_training_bars": initial_train_end,
        "folds": fold_results,
        "tested_scenarios": {
            name: {"spread_multiplier": mult[0], "slippage_multiplier": mult[1],
                   "commission_multiplier": mult[2]} for name, mult in SCENARIOS.items()
        },
        "folds_with_selected_champion": len(selected),
        "folds_without_champion": folds - len(selected),
        "all_fold_champions_preselected": all_selected,
        "total_baseline_oos_trades": sum(r["trades"] for r in baseline),
        "total_baseline_oos_net_pnl_usd": round(sum(r["net_pnl_usd"] for r in baseline), 6),
        "total_cost_shock_oos_net_pnl_usd": round(sum(r["net_pnl_usd"] for r in shock), 6),
        "historical_cost_robustness_candidate": indicative,
        "p_values_or_multiple_testing_adjustment_verified": False,
        "real_broker_data_origin_verified": False,
        "demo_forward_verified": False,
        "commercial_ready": False,
        "realized_profit_verified": False,
        "live_trades": 0,
        "order_execution_enabled": False,
        "warning": "Synthetic data and backtests never prove sustainable income. Source authentication, financing, spread/commission verification, independent statistics and broker forward receipts remain necessary.",
    }


def main():
    """Run read-only walk-forward on a provided local broker quote extract."""
    import argparse
    import json
    from pathlib import Path
    from trading.mojtrade_costed_oos import Settings, parse_bars

    parser = argparse.ArgumentParser(
        description="Research-only XAUUSD multi-fold cost-stress validation; zero broker orders"
    )
    parser.add_argument("--bid-ask-csv", required=True, type=Path)
    parser.add_argument("--settings-json", required=True, type=Path)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--test-bars", type=int, default=100)
    args = parser.parse_args()
    try:
        cfg = Settings.load(args.settings_json)
        bars, digest = parse_bars(args.bid_ask_csv, cfg.timeframe_minutes)
        result = walk_forward(bars, digest, cfg, folds=args.folds, test_bars=args.test_bars)
        print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
    except (ResearchError, OSError) as exc:
        parser.exit(2, f"MOJTRADE_WALK_FORWARD_REJECTED: {exc}\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reproducible, no-lookahead research backtest for OMEGA X.

Input CSV columns: timestamp,open,high,low,close[,spread_pips]
Signals are evaluated at a completed bar and entered at the next bar open.
This is a research harness only; it is not a broker adapter or trading advice.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Bar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    spread_pips: float = 0.0


@dataclass
class Trade:
    entry_time: str
    exit_time: str
    side: str
    entry: float
    exit: float
    pnl: float
    reason: str


def ema(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        raise ValueError("not enough bars for EMA")
    result = [math.nan] * len(values)
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    alpha = 2.0 / (period + 1)
    for i in range(period, len(values)):
        result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]
    return result


def atr(bars: list[Bar], period: int) -> list[float]:
    if len(bars) < period + 1:
        raise ValueError("not enough bars for ATR")
    tr = [math.nan]
    for i in range(1, len(bars)):
        tr.append(max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i - 1].close),
            abs(bars[i].low - bars[i - 1].close),
        ))
    result = [math.nan] * len(bars)
    result[period] = sum(tr[1 : period + 1]) / period
    for i in range(period + 1, len(bars)):
        result[i] = ((result[i - 1] * (period - 1)) + tr[i]) / period
    return result


def load_bars(path: Path) -> list[Bar]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"timestamp", "open", "high", "low", "close"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("CSV must contain timestamp,open,high,low,close")
    bars = []
    for row in rows:
        values = [float(row[key]) for key in ("open", "high", "low", "close")]
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError("invalid OHLC value")
        spread = float(row.get("spread_pips", 0) or 0)
        if not math.isfinite(spread) or spread < 0:
            raise ValueError("invalid spread_pips")
        bars.append(Bar(row["timestamp"], *values, spread))
    return bars


def run(bars: list[Bar], initial_equity: float, risk_pct: float,
        fast_period: int, slow_period: int, breakout_period: int,
        atr_period: int, atr_stop: float, reward_risk: float,
        commission_rate: float, slippage_pips: float) -> dict:
    closes = [bar.close for bar in bars]
    fast = ema(closes, fast_period)
    slow = ema(closes, slow_period)
    ranges = atr(bars, atr_period)
    equity = initial_equity
    peak = equity
    max_drawdown = 0.0
    trades: list[Trade] = []
    i = max(slow_period, breakout_period, atr_period) + 1

    while i < len(bars) - 1:
        prior_high = max(bar.high for bar in bars[i - breakout_period:i])
        prior_low = min(bar.low for bar in bars[i - breakout_period:i])
        side = None
        if fast[i] > slow[i] and bars[i].close > prior_high:
            side = "buy"
        elif fast[i] < slow[i] and bars[i].close < prior_low:
            side = "sell"
        if side is None or not math.isfinite(ranges[i]) or ranges[i] <= 0:
            i += 1
            continue

        entry_bar = bars[i + 1]
        spread = max(entry_bar.spread_pips, 0.0) + slippage_pips
        pip = max(entry_bar.close * 1e-5, 1e-8)
        entry = entry_bar.open + spread * pip if side == "buy" else entry_bar.open - spread * pip
        stop_distance = max(ranges[i] * atr_stop, pip)
        target_distance = stop_distance * reward_risk
        stop = entry - stop_distance if side == "buy" else entry + stop_distance
        target = entry + target_distance if side == "buy" else entry - target_distance
        risk_cash = equity * risk_pct / 100.0
        units = risk_cash / stop_distance
        exit_price = None
        reason = "end_of_data"
        exit_index = len(bars) - 1

        for j in range(i + 1, len(bars)):
            bar = bars[j]
            if side == "buy":
                hit_stop, hit_target = bar.low <= stop, bar.high >= target
            else:
                hit_stop, hit_target = bar.high >= stop, bar.low <= target
            # Conservative same-bar policy: stop is assumed first.
            if hit_stop:
                exit_price, reason, exit_index = stop, "stop", j
                break
            if hit_target:
                exit_price, reason, exit_index = target, "target", j
                break

        if exit_price is None:
            exit_price = bars[-1].close
        gross = (exit_price - entry) * units if side == "buy" else (entry - exit_price) * units
        fees = abs(entry * units) * commission_rate / 100.0 + abs(exit_price * units) * commission_rate / 100.0
        pnl = gross - fees
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        trades.append(Trade(entry_bar.timestamp, bars[exit_index].timestamp, side, entry, exit_price, pnl, reason))
        i = max(i + 1, exit_index + 1)

    wins = sum(trade.pnl > 0 for trade in trades)
    losses = sum(trade.pnl < 0 for trade in trades)
    return {
        "bars": len(bars),
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(100 * wins / len(trades), 4) if trades else 0.0,
        "initial_equity": initial_equity,
        "final_equity": round(equity, 8),
        "net_pnl": round(equity - initial_equity, 8),
        "max_drawdown": round(max_drawdown, 8),
        "cost_model": {"commission_rate_pct_per_side": commission_rate, "slippage_pips": slippage_pips},
        "lookahead_policy": "signal_on_closed_bar_entry_on_next_open",
        "status": "research_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--initial-equity", type=float, default=10000.0)
    parser.add_argument("--risk-pct", type=float, default=0.25)
    parser.add_argument("--commission-rate", type=float, default=0.0)
    parser.add_argument("--slippage-pips", type=float, default=0.0)
    parser.add_argument("--fast", type=int, default=8)
    parser.add_argument("--slow", type=int, default=34)
    parser.add_argument("--breakout", type=int, default=20)
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--atr-stop", type=float, default=2.0)
    parser.add_argument("--reward-risk", type=float, default=1.8)
    args = parser.parse_args()
    if args.initial_equity <= 0 or not 0 < args.risk_pct <= 1:
        raise SystemExit("invalid equity or risk")
    result = run(load_bars(args.csv), args.initial_equity, args.risk_pct,
                 args.fast, args.slow, args.breakout, args.atr_period,
                 args.atr_stop, args.reward_risk, args.commission_rate,
                 args.slippage_pips)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

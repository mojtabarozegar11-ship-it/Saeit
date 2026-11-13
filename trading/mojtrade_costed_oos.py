"""Cost-aware, strictly chronological MojTrade strategy selection on actual bid/ask bars.

No broker calls and no fake prices. Research results require a separately
sourced XAUUSD broker bid/ask CSV and explicit execution-cost assumptions.
A passing historical test NEVER authorizes orders or proves future profit.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from trading.mojtrade_market_sessions import (
    SessionGapError, load_closure_claims, reconcile_gaps,
)

FIELDS = ("timestamp_utc", "bid_open", "bid_high", "bid_low", "bid_close",
          "ask_open", "ask_high", "ask_low", "ask_close")
STRATEGIES = ("ema_8_21", "ema_13_34", "breakout_20", "mean_revert_20")
MIN_BARS = 300
MAX_BARS = 750_000
MODEL = "mojtrade-costed-oos-xauusd-v1"


class ResearchError(ValueError):
    pass


def number(value, field, *, minimum=None, allow_zero=False):
    if isinstance(value, bool) or value is None:
        raise ResearchError(field + "_invalid")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ResearchError(field + "_invalid") from exc
    if not math.isfinite(result):
        raise ResearchError(field + "_not_finite")
    if minimum is not None and (result < minimum or (not allow_zero and result == minimum)):
        raise ResearchError(field + "_out_of_bounds")
    return result


@dataclass(frozen=True)
class Bar:
    time: datetime
    bo: float
    bh: float
    bl: float
    bc: float
    ao: float
    ah: float
    al: float
    ac: float

    def midpoint(self, component):
        return (getattr(self, "b" + component) + getattr(self, "a" + component)) / 2


def parse_bars(path: Path, timeframe: int, closure_claims=None):
    if path.is_symlink() or not path.is_file():
        raise ResearchError("source_not_regular_or_symlink")
    sha = hashlib.sha256()
    bars = []
    with path.open("rb") as f:
        # Preserve the exact input bytes and refuse deceptive oversized files.
        raw = f.read(200_000_001)
    if len(raw) > 200_000_000:
        raise ResearchError("source_oversized")
    sha.update(raw)
    try:
        text = raw.decode("utf-8-sig")
        import io
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames != list(FIELDS):
            raise ResearchError("quote_columns_must_match_exact_schema")
        for row in reader:
            if len(bars) >= MAX_BARS:
                raise ResearchError("too_many_bars")
            if None in row or any(v is None for v in row.values()):
                raise ResearchError("malformed_csv_row")
            try:
                at = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
            except (ValueError, TypeError, AttributeError) as exc:
                raise ResearchError("timestamp_invalid") from exc
            if at.tzinfo is None or at.utcoffset().total_seconds() != 0:
                raise ResearchError("timestamp_must_be_utc")
            values = [number(row[k], k, minimum=0) for k in FIELDS[1:]]
            bo, bh, bl, bc, ao, ah, al, ac = values
            if (not bl <= min(bo, bc) <= max(bo, bc) <= bh
                    or not al <= min(ao, ac) <= max(ao, ac) <= ah
                    or any(x > y for x, y in ((bo, ao), (bh, ah), (bl, al), (bc, ac)))):
                raise ResearchError("crossed_or_impossible_bid_ask")
            if int(at.timestamp()) % (timeframe * 60):
                raise ResearchError("quote_timestamp_timeframe_misaligned")
            if bars:
                delta = (at - bars[-1].time).total_seconds()
                if delta <= 0 or delta % (timeframe * 60):
                    raise ResearchError("missing_duplicate_or_out_of_order_bar")
            bars.append(Bar(at, *values))
    except UnicodeDecodeError as exc:
        raise ResearchError("source_not_utf8") from exc
    if len(bars) < MIN_BARS:
        raise ResearchError("insufficient_chronological_bars")
    try:
        reconcile_gaps(bars, timeframe, closure_claims or [])
    except SessionGapError as exc:
        raise ResearchError(str(exc)) from exc
    return bars, sha.hexdigest()


@dataclass(frozen=True)
class Settings:
    timeframe_minutes: int
    initial_equity_usd: float
    commission_usd_per_ounce_per_side: float
    slippage_usd_per_ounce_per_side: float
    quantity_step_ounces: float
    max_notional_to_equity: float
    risk_fraction: float
    stop_atr_multiple: float
    reward_to_risk: float
    max_hold_bars: int

    @classmethod
    def load(cls, path: Path):
        if path.is_symlink() or not path.is_file():
            raise ResearchError("settings_source_not_regular")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ResearchError("settings_json_invalid") from exc
        keys = ("timeframe_minutes", "initial_equity_usd",
                "commission_usd_per_ounce_per_side", "slippage_usd_per_ounce_per_side",
                "quantity_step_ounces", "max_notional_to_equity", "risk_fraction",
                "stop_atr_multiple", "reward_to_risk", "max_hold_bars")
        if not isinstance(value, dict) or set(value) != set(keys):
            raise ResearchError("settings_schema_invalid")
        for key in ("timeframe_minutes", "max_hold_bars"):
            if type(value[key]) is not int or value[key] <= 0:
                raise ResearchError(key + "_invalid")
        if value["timeframe_minutes"] not in (1, 5, 10):
            raise ResearchError("unsupported_timeframe")
        if not 1 <= value["max_hold_bars"] <= 200:
            raise ResearchError("max_hold_bars_out_of_bounds")
        cleaned = dict(value)
        for key in keys:
            if key in ("timeframe_minutes", "max_hold_bars"):
                continue
            cleaned[key] = number(value[key], key, minimum=0,
                                  allow_zero=("commission" in key or "slippage" in key))
        # LiteFinance's published XAUUSD contract size is 100 oz/lot
        # with a listed 0.01-lot step, i.e. 1 oz. Micro-ounce fills would
        # fabricate otherwise unavailable trading capacity. Account-level
        # contract specifications must still be independently reconciled.
        if cleaned["quantity_step_ounces"] != 1.0:
            raise ResearchError("litefinance_xauusd_requires_one_ounce_lot_step")
        if not 0 < cleaned["risk_fraction"] <= 0.02:
            raise ResearchError("risk_fraction_out_of_bounds")
        if not 0 < cleaned["max_notional_to_equity"] <= 50:
            raise ResearchError("notional_leverage_requires_verified_limit")
        return cls(**cleaned)


def ema(series, period):
    out = []
    last = None
    alpha = 2 / (period + 1)
    for i, value in enumerate(series):
        last = value if last is None else alpha * value + (1 - alpha) * last
        out.append(last if i >= period - 1 else None)
    return out


def indicators(bars):
    closes = [bar.midpoint("c") for bar in bars]
    highs = [bar.midpoint("h") for bar in bars]
    lows = [bar.midpoint("l") for bar in bars]
    tr = [highs[0] - lows[0]]
    for i in range(1, len(bars)):
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i-1]),
                      abs(lows[i] - closes[i-1])))
    atr = [None] * len(bars)
    running = 0
    for i, val in enumerate(tr):
        if i < 14:
            running += val
            if i == 13:
                running /= 14
        else:
            running = (13 * running + val) / 14
        if i >= 13:
            atr[i] = running
    return closes, highs, lows, atr, {p: ema(closes, p) for p in (8, 13, 21, 34)}


def signal_at(i, strategy, data):
    closes, highs, lows, atr, emas = data
    if i < 40 or atr[i] is None or atr[i] <= 0:
        return 0
    if strategy.startswith("ema_"):
        short, long = ((8, 21) if strategy == "ema_8_21" else (13, 34))
        prev, curr = emas[short][i-1] - emas[long][i-1], emas[short][i] - emas[long][i]
        return 1 if prev <= 0 < curr else (-1 if prev >= 0 > curr else 0)
    if strategy == "breakout_20":
        return 1 if closes[i] > max(highs[i-20:i]) else (
            -1 if closes[i] < min(lows[i-20:i]) else 0)
    if strategy == "mean_revert_20":
        mean = sum(closes[i-20:i]) / 20
        volatility = math.sqrt(sum((v - mean) ** 2 for v in closes[i-20:i]) / 20)
        if volatility <= 0:
            return 0
        return 1 if closes[i] < mean - 1.5 * volatility else (
            -1 if closes[i] > mean + 1.5 * volatility else 0)
    raise ResearchError("unknown_strategy")


def _close(position, bar, *, forced=False, settings=None):
    side, entry, stop, take, quantity, opened, entry_commission = position
    slip = settings.slippage_usd_per_ounce_per_side
    if side == 1:
        if bar.bo <= stop:
            exit_price, reason = bar.bo - slip, "gap_stop"
        elif bar.bl <= stop:
            exit_price, reason = stop - slip, "stop"
        elif bar.bh >= take:
            exit_price, reason = take - slip, "take"
        elif forced:
            exit_price, reason = bar.bc - slip, "time_or_segment_end"
        else:
            return None
    else:
        if bar.ao >= stop:
            exit_price, reason = bar.ao + slip, "gap_stop"
        elif bar.ah >= stop:
            exit_price, reason = stop + slip, "stop"
        elif bar.al <= take:
            exit_price, reason = take + slip, "take"
        elif forced:
            exit_price, reason = bar.ac + slip, "time_or_segment_end"
        else:
            return None
    gross = (exit_price - entry) * side * quantity
    fees = quantity * settings.commission_usd_per_ounce_per_side * 2
    return {
        "gross": gross, "fees": fees, "net": gross - fees,
        "reason": reason, "quantity_ounces": quantity,
        "bars_held": None, "entry_spread_included": True,
    }


def simulate(bars, data, cfg, strategy, start, end):
    """All signals at closed bar i; entries strictly at i+1 open."""
    equity = cfg.initial_equity_usd
    peak = equity
    worst_drawdown = 0.0
    worst_intrabar_drawdown = 0.0
    trades = []
    position = None
    pending = None
    realized_today = 0.0
    day_start_equity = equity
    current_day = None
    skipped_minimum_size = 0
    stale_signals_discarded_at_market_reopen = 0
    for i in range(start, end):
        bar = bars[i]
        day = bar.time.date()
        if day != current_day:
            current_day = day
            realized_today = 0
            day_start_equity = equity
        # A Friday close or pre-holiday closed-bar signal cannot be filled at
        # Monday's first quote as if the intervening market were liquid.
        if (
            i > start and pending is not None
            and (bar.time - bars[i-1].time).total_seconds() != cfg.timeframe_minutes * 60
        ):
            pending = None
            stale_signals_discarded_at_market_reopen += 1
        if position is None and pending is not None and equity > 0:
            side, stop_distance = pending
            pending = None
            if realized_today > -(day_start_equity * 0.02):
                entry = (bar.ao + cfg.slippage_usd_per_ounce_per_side
                         if side == 1 else bar.bo - cfg.slippage_usd_per_ounce_per_side)
                # Quote spread is already charged via ask/bid fills; do not double-count.
                gap_spread = bar.ao - bar.bo
                unit_risk = (stop_distance + gap_spread
                             + cfg.slippage_usd_per_ounce_per_side * 2
                             + cfg.commission_usd_per_ounce_per_side * 2)
                if unit_risk > 0 and entry > 0:
                    risk_qty = equity * cfg.risk_fraction / unit_risk
                    notional_qty = equity * cfg.max_notional_to_equity / entry
                    qty = (math.floor(min(risk_qty, notional_qty)
                                      / cfg.quantity_step_ounces)
                           * cfg.quantity_step_ounces)
                    if qty >= cfg.quantity_step_ounces:
                        stop = entry - side * stop_distance
                        take = entry + side * stop_distance * cfg.reward_to_risk
                        if stop > 0 and take > 0:
                            position = (side, entry, stop, take, qty, i,
                                        qty * cfg.commission_usd_per_ounce_per_side)
                    else:
                        skipped_minimum_size += 1
        if position is not None:
            side, entry, _stop, _take, qty, _opened, _fee = position
            # Stress mark on the adverse intrabar quote, including possible
            # slippage and both commissions. It is NOT a live equity statement.
            adverse_exit = (bar.bl - cfg.slippage_usd_per_ounce_per_side
                            if side == 1 else bar.ah + cfg.slippage_usd_per_ounce_per_side)
            stress_pnl = ((adverse_exit - entry) * side * qty
                          - 2 * qty * cfg.commission_usd_per_ounce_per_side)
            worst_intrabar_drawdown = max(
                worst_intrabar_drawdown, max(0.0, peak - (equity + stress_pnl)) / peak
            )
            forced = (i - position[5] >= cfg.max_hold_bars or i == end - 1)
            outcome = _close(position, bar, forced=forced, settings=cfg)
            if outcome is not None:
                outcome["bars_held"] = i - position[5] + 1
                outcome["entry_index"] = position[5]
                outcome["exit_index"] = i
                trades.append(outcome)
                equity += outcome["net"]
                realized_today += outcome["net"]
                peak = max(peak, equity)
                worst_drawdown = max(worst_drawdown, (peak - equity) / peak)
                position = None
        if i + 1 < end and position is None and equity > 0 and realized_today > -(day_start_equity * 0.02):
            side = signal_at(i, strategy, data)
            atr = data[3][i]
            pending = ((side, atr * cfg.stop_atr_multiple)
                       if side and atr and atr > 0 else None)
        else:
            pending = None
    wins = [t["net"] for t in trades if t["net"] > 0]
    losses = [t["net"] for t in trades if t["net"] < 0]
    gross_gain = sum(wins)
    gross_loss = -sum(losses)
    return {
        "trades": len(trades),
        "net_pnl_usd": round(equity - cfg.initial_equity_usd, 6),
        "ending_equity_usd": round(equity, 6),
        "win_rate": round(len(wins) / len(trades), 6) if trades else None,
        "profit_factor": round(gross_gain / gross_loss, 6) if gross_loss > 0 else None,
        "max_closed_equity_drawdown_fraction": round(worst_drawdown, 6),
        "max_intrabar_stress_drawdown_fraction": round(
            max(worst_intrabar_drawdown, worst_drawdown), 6
        ),
        "commissions_usd": round(sum(t["fees"] for t in trades), 6),
        "stops": sum(t["reason"] in ("stop", "gap_stop") for t in trades),
        "gap_stops": sum(t["reason"] == "gap_stop" for t in trades),
        "skipped_minimum_size": skipped_minimum_size,
        "stale_signals_discarded_at_market_reopen": stale_signals_discarded_at_market_reopen,
        "entry_is_next_bar": True,
        "intrabar_stop_first_if_both_touched": True,
        "result_type": "unverified_historical_simulation_not_realized_profit",
    }


def evaluate(bars, source_digest, cfg):
    data = indicators(bars)
    n = len(bars)
    training_end = int(n * 0.60)
    embargo = max(40, cfg.max_hold_bars)
    test_start = training_end + embargo
    if test_start + 100 >= n:
        raise ResearchError("insufficient_embargoed_holdout")
    trials = [
        (strategy, simulate(bars, data, cfg, strategy, 40, training_end))
        for strategy in STRATEGIES
    ]
    # Selection is TRAINING ONLY. Record all failed configurations too.
    eligible = [item for item in trials if item[1]["trades"] >= 5
                and item[1]["net_pnl_usd"] > 0
                and item[1]["max_closed_equity_drawdown_fraction"] < 0.25]
    winner = (max(eligible, key=lambda x: (x[1]["net_pnl_usd"], x[0]))
              if eligible else None)
    heldout = (simulate(bars, data, cfg, winner[0], test_start, n)
               if winner else None)
    return {
        "schema": MODEL,
        "symbol": "XAUUSD",
        "source_sha256": source_digest,
        "source_is_cryptographically_authenticated_to_broker": False,
        "bid_ask_ohlc_required_by_input_contract": True,
        "broker_quote_provenance_unverified": True,
        "timeframe_minutes": cfg.timeframe_minutes,
        "input_bars": n,
        "train_bars": training_end - 40,
        "embargo_bars": embargo,
        "holdout_bars": n - test_start,
        "strategies_examined": list(STRATEGIES),
        "trials_count": len(trials),
        "all_training_results": {name: result for name, result in trials},
        "train_selected_strategy": winner[0] if winner else None,
        "heldout_result": heldout,
        "historical_edge_candidate": bool(
            heldout and heldout["trades"] >= 5
            and heldout["net_pnl_usd"] > 0
            and heldout["profit_factor"] is not None
            and heldout["profit_factor"] > 1.05),
        "statistical_significance_verified": False,
        "walk_forward_multi_fold_verified": False,
        "broker_forward_demo_verified": False,
        "market_order_placement_enabled": False,
        "live_trades": 0,
        "realized_profit_verified": False,
        "commercial_ready": False,
        "warning": "Historical simulation, not banked income; selection and costs require independent broker/demo reconciliation.",
    }


def main():
    parser = argparse.ArgumentParser(description="MojTrade real-quote research — no broker operations")
    parser.add_argument("--bid-ask-csv", required=True, type=Path)
    parser.add_argument("--settings-json", required=True, type=Path)
    parser.add_argument("--session-closures-json", type=Path,
                        help="Optional broker-specific claimed closures; not independently authenticated")
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()
    try:
        cfg = Settings.load(args.settings_json)
        claims, calendar_sha = (
            load_closure_claims(args.session_closures_json, cfg.timeframe_minutes)
            if args.session_closures_json else ([], None)
        )
        bars, digest = parse_bars(args.bid_ask_csv, cfg.timeframe_minutes, claims)
        report = evaluate(bars, digest, cfg)
        report["market_closure_claims_used"] = len(claims)
        report["market_closure_manifest_sha256"] = calendar_sha
        report["market_closure_broker_origin_verified"] = False
        rendered = json.dumps(report, sort_keys=True, indent=2, allow_nan=False)
        if args.report_json is not None:
            # Avoid publishing account data or research in a public site directory.
            destination = args.report_json
            if destination.is_symlink() or any(p.lower() in {"public_html", "www", "htdocs"}
                                              for p in destination.parts):
                raise ResearchError("public_or_symlink_report_rejected")
            destination.write_text(rendered + "\n", encoding="utf-8")
        else:
            print(rendered)
    except (ResearchError, SessionGapError, OSError) as exc:
        parser.exit(2, f"MOJTRADE_OOS_REJECTED: {exc}\n")


if __name__ == "__main__":
    main()

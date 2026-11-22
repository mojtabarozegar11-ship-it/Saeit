#!/usr/bin/env python3
"""MojTrade portfolio-wide research slot reservation, NEVER a broker approval.

Python standard library only. No network, orders, broker imports, funds,
signals, email, or background loop. SQLite transactions serialize competing
research requests. Input prices / portfolio snapshots are untrusted research
assertions, not verified broker state. Never wire outputs directly to orders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


SCHEMA = "mojtrade.portfolio-risk-research.v1"
GROUPS = {
    "EURUSD": "USD_FX", "GBPUSD": "USD_FX", "USDJPY": "USD_FX",
    "XAUUSD": "METALS", "XAGUSD": "METALS",
    "BTCUSD": "CRYPTO", "ETHUSD": "CRYPTO",
}
MAX_BATCH = 32
MAX_EXISTING = 200
MAX_HISTORY_ROWS = 512
MAX_INPUT_BYTES = 256_000
D = Decimal
POLICY = {
    "individual_fraction": D("0.0025"),
    "aggregate_fraction": D("0.012"),
    "symbol_fraction": D("0.005"),
    "cluster_fraction": D("0.008"),
    "strategy_fraction": D("0.005"),
    "gross_notional_multiple": D("3.0"),
    "daily_drawdown_fraction": D("0.015"),
    "global_drawdown_fraction": D("0.05"),
    "max_positions": 10,
    "max_symbol_positions": 3,
    "max_strategy_positions": 3,
    "consecutive_losses_stop": 4,
    "max_snapshot_lag_seconds": 5,
    "max_quote_lag_seconds": 3,
}
POLICY_ID = "MT-RISK-FROZEN-RESEARCH-20261107"


class RiskReject(ValueError):
    """Invalid evidence or unsafe research reservation request."""


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _dec(value, key, *, gt=None, ge=None):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise RiskReject(key + "_type")
    if isinstance(value, str) and (len(value) > 32 or not value):
        raise RiskReject(key + "_length")
    try:
        result = D(str(value))
    except Exception as exc:
        raise RiskReject(key + "_invalid") from exc
    if not result.is_finite() or result > D("1e15") or result.as_tuple().exponent < -12:
        raise RiskReject(key + "_nonfinite_or_unbounded")
    if gt is not None and result <= D(gt):
        raise RiskReject(key + "_nonpositive")
    if ge is not None and result < D(ge):
        raise RiskReject(key + "_negative")
    return result


def _name(value, key, max_len=64):
    if (not isinstance(value, str) or not 1 <= len(value) <= max_len or
            not value.isascii() or
            not all(ch.isalnum() or ch in "-_." for ch in value)):
        raise RiskReject(key + "_invalid")
    return value


def _utc(value):
    if not isinstance(value, str):
        raise RiskReject("time_type")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RiskReject("time_parse") from exc
    if dt.tzinfo is None:
        raise RiskReject("time_not_utc")
    return dt.astimezone(timezone.utc)


def _leg(item, *, existing):
    key = "position_id" if existing else "request_id"
    mandatory = {key, "symbol", "strategy_id", "side", "quantity", "entry",
                 "stop", "unit_value_cash_per_price_point", "execution_buffer_cash"}
    if not isinstance(item, dict) or set(item) != mandatory:
        raise RiskReject("leg_schema")
    identity = _name(item[key], key)
    symbol = _name(item["symbol"], "symbol", 16)
    if symbol not in GROUPS:
        raise RiskReject("symbol_not_in_frozen_map")
    strategy = _name(item["strategy_id"], "strategy_id")
    side = item["side"]
    if side not in ("BUY", "SELL"):
        raise RiskReject("side_invalid")
    quantity = _dec(item["quantity"], "quantity", gt=0)
    entry = _dec(item["entry"], "entry", gt=0)
    stop = _dec(item["stop"], "stop", gt=0)
    point = _dec(item["unit_value_cash_per_price_point"], "point", gt=0)
    buffer = _dec(item["execution_buffer_cash"], "buffer", ge=0)
    if (side == "BUY" and stop >= entry) or (side == "SELL" and stop <= entry):
        raise RiskReject("stop_not_adverse")
    notional = entry * quantity * point
    # Floor is illustrative and cannot substitute for actual market slippage.
    minimum_buffer = notional * D("0.0002")
    if buffer < minimum_buffer:
        raise RiskReject("execution_buffer_below_research_floor")
    risk = abs(entry - stop) * quantity * point + buffer
    if risk <= 0 or risk > D("1e15") or notional > D("1e15"):
        raise RiskReject("leg_risk_unbounded")
    return {"id": identity, "symbol": symbol, "cluster": GROUPS[symbol],
            "strategy_id": strategy, "side": side, "risk": risk,
            "notional": notional, "fingerprint": _digest(item)}


def _parse_request(payload, now):
    required = {"account_id", "account_mode", "risk_day", "snapshot_at", "quote_at",
                "equity_cash", "day_start_equity_cash", "peak_equity_cash",
                "consecutive_losses", "open_positions", "proposals"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise RiskReject("request_schema")
    account = _name(payload["account_id"], "account_id")
    if payload["account_mode"] != "DEMO":
        raise RiskReject("live_account_permanently_rejected")
    day = payload["risk_day"]
    if not isinstance(day, str) or day != now.date().isoformat():
        raise RiskReject("risk_day_not_current_utc")
    snapshot_at = _utc(payload["snapshot_at"])
    quote_at = _utc(payload["quote_at"])
    if ((now - snapshot_at).total_seconds() < 0 or
            (now - snapshot_at).total_seconds() > POLICY["max_snapshot_lag_seconds"]):
        raise RiskReject("stale_or_future_account_snapshot")
    if ((now - quote_at).total_seconds() < 0 or
            (now - quote_at).total_seconds() > POLICY["max_quote_lag_seconds"] or
            quote_at > snapshot_at):
        raise RiskReject("stale_or_future_market_quote")
    equity = _dec(payload["equity_cash"], "equity", gt=0)
    anchor = _dec(payload["day_start_equity_cash"], "day_anchor", gt=0)
    peak = _dec(payload["peak_equity_cash"], "peak", gt=0)
    if equity > peak or anchor > peak:
        raise RiskReject("peak_equity_inconsistent")
    losses = payload["consecutive_losses"]
    if type(losses) is not int or not 0 <= losses <= 100_000:
        raise RiskReject("consecutive_losses_invalid")
    raw_positions, raw_proposals = payload["open_positions"], payload["proposals"]
    if (not isinstance(raw_positions, list) or len(raw_positions) > MAX_EXISTING or
            not isinstance(raw_proposals, list) or
            not 1 <= len(raw_proposals) <= MAX_BATCH):
        raise RiskReject("batch_size_invalid")
    positions = [_leg(item, existing=True) for item in raw_positions]
    proposals = [_leg(item, existing=False) for item in raw_proposals]
    if len({x["id"] for x in positions}) != len(positions):
        raise RiskReject("duplicate_position_id")
    if len({x["id"] for x in proposals}) != len(proposals):
        raise RiskReject("duplicate_request_id")
    return {"account": account, "day": day, "snapshot_at": snapshot_at,
            "equity": equity, "anchor": anchor, "peak": peak, "losses": losses,
            "positions": positions, "proposals": proposals}


def _current_capacity(legs):
    sums = {"risk": D(0), "notional": D(0), "count": 0,
            "symbol_risk": {}, "cluster_risk": {}, "strategy_risk": {},
            "symbol_count": {}, "strategy_count": {}}
    for leg in legs:
        sums["risk"] += leg["risk"]
        sums["notional"] += leg["notional"]
        sums["count"] += 1
        for source, field, increment in (
            ("symbol_risk", "symbol", leg["risk"]),
            ("cluster_risk", "cluster", leg["risk"]),
            ("strategy_risk", "strategy_id", leg["risk"]),
            ("symbol_count", "symbol", 1),
            ("strategy_count", "strategy_id", 1),
        ):
            key = leg[field]
            sums[source][key] = sums[source].get(key, 0) + increment
    return sums


def _reasons(leg, all_legs, equity):
    sums = _current_capacity(all_legs)
    after = _current_capacity([*all_legs, leg])
    reasons = []
    if leg["risk"] > equity * POLICY["individual_fraction"]:
        reasons.append("individual_loss_budget")
    if after["risk"] > equity * POLICY["aggregate_fraction"]:
        reasons.append("aggregate_stop_loss_budget")
    if after["symbol_risk"].get(leg["symbol"], 0) > equity * POLICY["symbol_fraction"]:
        reasons.append("symbol_concentration_budget")
    if after["cluster_risk"].get(leg["cluster"], 0) > equity * POLICY["cluster_fraction"]:
        reasons.append("cluster_concentration_budget")
    if after["strategy_risk"].get(leg["strategy_id"], 0) > equity * POLICY["strategy_fraction"]:
        reasons.append("strategy_concentration_budget")
    if after["notional"] > equity * POLICY["gross_notional_multiple"]:
        reasons.append("gross_notional_budget")
    if sums["count"] >= POLICY["max_positions"]:
        reasons.append("position_count_budget")
    if sums["symbol_count"].get(leg["symbol"], 0) >= POLICY["max_symbol_positions"]:
        reasons.append("symbol_position_count_budget")
    if sums["strategy_count"].get(leg["strategy_id"], 0) >= POLICY["max_strategy_positions"]:
        reasons.append("strategy_position_count_budget")
    return reasons


def _private_db(path):
    path = Path(path)
    parent = path.parent
    if (not parent.is_dir() or parent.is_symlink() or
            stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise RiskReject("private_directory_0700_required")
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise RiskReject("nonregular_or_symlink_db_rejected")
    if not path.exists():
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            pass  # A second process may have just created the same private DB.
        else:
            os.close(fd)
    meta = os.stat(path, follow_symlinks=False)
    if (not stat.S_ISREG(meta.st_mode) or stat.S_IMODE(meta.st_mode) != 0o600 or
            meta.st_uid != os.geteuid() or meta.st_nlink != 1):
        raise RiskReject("private_db_owner_permissions_invalid")
    con = sqlite3.connect(str(path), timeout=15, isolation_level=None)
    con.execute("PRAGMA synchronous=FULL")
    con.execute("PRAGMA busy_timeout=15000")
    return con


def _schema(con):
    con.execute("""CREATE TABLE IF NOT EXISTS account_state (
        account TEXT PRIMARY KEY, day TEXT NOT NULL, anchor TEXT NOT NULL,
        peak TEXT NOT NULL, max_losses INTEGER NOT NULL,
        last_snapshot TEXT NOT NULL, latched INTEGER NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS decisions (
        account TEXT NOT NULL, request_id TEXT NOT NULL,
        payload_hash TEXT NOT NULL, decision_json TEXT NOT NULL,
        approved_risk TEXT NOT NULL, approved_notional TEXT NOT NULL,
        symbol TEXT NOT NULL, cluster TEXT NOT NULL, strategy TEXT NOT NULL,
        PRIMARY KEY(account, request_id))""")


def reserve_research_slots(payload, db_path, *, now=None):
    """Serialize all requests with BEGIN IMMEDIATE. NEVER returns order consent.

    Approved reservations are intentionally never auto-expired or deleted:
    broker reconciliation / release is *not* implemented. This can exhaust
    the research budget, but cannot silently free capital still exposed.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise RiskReject("now_not_utc")
    now = now.astimezone(timezone.utc)
    request = _parse_request(payload, now)
    con = _private_db(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        _schema(con)
        history_count = con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        if history_count + len(request["proposals"]) > MAX_HISTORY_ROWS:
            raise RiskReject("audit_history_budget_exhausted")
        row = con.execute("SELECT day,anchor,peak,max_losses,last_snapshot,latched "
                          "FROM account_state WHERE account=?", (request["account"],)).fetchone()
        if row:
            old_day, old_anchor, old_peak, old_losses, old_time, latched = row
            if request["snapshot_at"] < _utc(old_time):
                raise RiskReject("snapshot_timestamp_regression")
            if request["day"] < old_day:
                raise RiskReject("risk_day_regression")
            if request["day"] == old_day:
                if request["anchor"] != D(old_anchor):
                    raise RiskReject("day_start_anchor_reset_attempt")
                if request["losses"] < old_losses:
                    raise RiskReject("loss_counter_reset_unverified")
            else:
                old_losses = 0
                latched = 0  # Daily latch resets only on UTC date transition.
            peak = max(D(old_peak), request["peak"], request["equity"])
        else:
            latched = 0
            old_losses = 0
            peak = request["peak"]
        equity, anchor = request["equity"], request["anchor"]
        day_stop = equity <= anchor * (1 - POLICY["daily_drawdown_fraction"])
        global_stop = equity <= peak * (1 - POLICY["global_drawdown_fraction"])
        losing = request["losses"] >= POLICY["consecutive_losses_stop"]
        latched = int(bool(latched or day_stop or global_stop or losing))
        con.execute("INSERT INTO account_state VALUES(?,?,?,?,?,?,?) "
                    "ON CONFLICT(account) DO UPDATE SET "
                    "day=excluded.day,anchor=excluded.anchor,peak=excluded.peak," 
                    "max_losses=excluded.max_losses,last_snapshot=excluded.last_snapshot," 
                    "latched=excluded.latched",
                    (request["account"], request["day"], str(anchor), str(peak),
                     max(old_losses, request["losses"]),
                     request["snapshot_at"].isoformat(), latched))
        held = []
        for rec in con.execute("SELECT approved_risk,approved_notional,symbol,cluster,strategy "
                               "FROM decisions WHERE account=? AND approved_risk != '0'",
                               (request["account"],)):
            held.append({"risk": D(rec[0]), "notional": D(rec[1]),
                         "symbol": rec[2], "cluster": rec[3], "strategy_id": rec[4]})
        exposure = [*request["positions"], *held]
        decisions = []
        for leg in request["proposals"]:
            past = con.execute("SELECT payload_hash,decision_json FROM decisions "
                               "WHERE account=? AND request_id=?",
                               (request["account"], leg["id"])).fetchone()
            if past:
                if past[0] != leg["fingerprint"]:
                    raise RiskReject("request_id_reused_with_different_payload")
                previous = json.loads(past[1])
                decisions.append(previous)
                continue
            reasons = []
            if latched:
                reasons.append("risk_circuit_breaker_latched")
            reasons.extend(_reasons(leg, exposure, equity))
            decision = {
                "request_id": leg["id"], "strategy_id": leg["strategy_id"],
                "symbol": leg["symbol"], "status": "REJECTED" if reasons else "RESEARCH_SLOT_RESERVED",
                "reasons": reasons, "risk_cash": str(leg["risk"]),
                "gross_notional_cash": str(leg["notional"]),
                "broker_eligible": False, "orders": 0, "execution": "disabled",
                "policy_id": POLICY_ID,
            }
            decision["receipt_sha256"] = _digest(decision)
            allowed = not reasons
            con.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?,?,?,?)",
                        (request["account"], leg["id"], leg["fingerprint"],
                         _canonical(decision), str(leg["risk"]) if allowed else "0",
                         str(leg["notional"]) if allowed else "0",
                         leg["symbol"], leg["cluster"], leg["strategy_id"]))
            decisions.append(decision)
            if allowed:
                exposure.append(leg)
        con.commit()
        response = {"schema": SCHEMA, "mode": "RESEARCH_ONLY", "execution": "disabled",
                    "orders": 0, "public_signals": 0, "policy_id": POLICY_ID,
                    "account_id": request["account"], "risk_day": request["day"],
                    "circuit_breaker_latched": bool(latched), "decisions": decisions,
                    "limitations": ["snapshot not independently authenticated",
                                    "cost and contract values are caller assertions",
                                    "not connected to broker reconciliation",
                                    "no automatic reservation release",
                                    "not an order permission"]}
        response["report_sha256"] = _digest(response)
        return response
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Research-only portfolio risk slot gate")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.input.is_symlink() or not args.input.is_file() or args.input.stat().st_size > MAX_INPUT_BYTES:
        raise RiskReject("unsafe_input")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = reserve_research_slots(payload, args.db)
    print(_canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

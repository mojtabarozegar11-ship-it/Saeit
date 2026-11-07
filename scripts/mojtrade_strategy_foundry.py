#!/usr/bin/env python3
"""MojTrade offline, research-only autonomous strategy invention.

No broker imports, network calls, order endpoints or paid services. Strategies
are typed data, not executable arbitrary Python/C#; all results are unproven
research hypotheses. Backtest fills are deliberately delayed and simplified.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import random
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = "mojtrade.strategy-foundry.v1"
ALLOWED_FEATURES = ("momentum", "mean_deviation", "range_location", "volatility_shift")
ALLOWED_HORIZONS = (1, 3, 5, 10)
ALLOWED_INTERVALS = (60, 180, 300, 600, 3600)
MAX_INPUT_BYTES = 1_000_000
MIN_BARS = 100
MAX_BARS = 5000
MAX_TRIALS = 96
MAX_REGISTRY_BYTES = 8_000_000
MAX_REGISTRY_ROWS = 128
MIN_TRAIN_EVENTS = 2
MAX_BEHAVIOR_OVERLAP = 0.90
WINDOWS = (6, 12, 24)


class FoundryError(ValueError):
    """Bad research inputs are rejected without making up data or trades."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _number(value, key, *, min_value=None, max_value=None):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise FoundryError(key + "_type")
    result = float(value)
    if not math.isfinite(result):
        raise FoundryError(key + "_finite")
    if min_value is not None and result < min_value:
        raise FoundryError(key + "_below_min")
    if max_value is not None and result > max_value:
        raise FoundryError(key + "_above_max")
    return result


def _timestamp(value):
    if not isinstance(value, str):
        raise FoundryError("timestamp_type")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FoundryError("timestamp_parse") from exc
    if dt.tzinfo is None:
        raise FoundryError("timestamp_not_utc")
    dt = dt.astimezone(timezone.utc)
    return dt


def validate_dataset(payload):
    if not isinstance(payload, dict) or set(payload) != {"source_id", "symbol", "interval_seconds", "bars"}:
        raise FoundryError("dataset_schema")
    source_id, symbol, interval, rows = (payload[k] for k in ("source_id", "symbol", "interval_seconds", "bars"))
    if not isinstance(source_id, str) or not (1 <= len(source_id) <= 80) or not source_id.isascii():
        raise FoundryError("source_identity")
    if not isinstance(symbol, str) or not (2 <= len(symbol) <= 32) or not all(c.isascii() and (c.isalnum() or c in "/-_") for c in symbol):
        raise FoundryError("symbol")
    if type(interval) is not int or interval not in ALLOWED_INTERVALS:
        raise FoundryError("interval")
    if not isinstance(rows, list) or not MIN_BARS <= len(rows) <= MAX_BARS:
        raise FoundryError("bar_count")
    bars = []
    last_t = None
    for raw in rows:
        if not isinstance(raw, dict) or set(raw) != {"t", "available_at", "open", "high", "low", "close", "spread_bps"}:
            raise FoundryError("bar_schema")
        stamp = _timestamp(raw["t"])
        available = _timestamp(raw["available_at"])
        if last_t is not None and (stamp - last_t).total_seconds() != interval:
            raise FoundryError("bar_gap_or_duplicate")
        if available < stamp or (available - stamp).total_seconds() > interval:
            raise FoundryError("bar_availability_invalid")
        last_t = stamp
        op = _number(raw["open"], "open", min_value=1e-12)
        hi = _number(raw["high"], "high", min_value=1e-12)
        lo = _number(raw["low"], "low", min_value=1e-12)
        cl = _number(raw["close"], "close", min_value=1e-12)
        spread = _number(raw["spread_bps"], "spread", min_value=0, max_value=500)
        if not lo <= min(op, cl) <= max(op, cl) <= hi:
            raise FoundryError("ohlc_integrity")
        bars.append({"t": stamp.isoformat(), "available_at": available.isoformat(),
                     "open": op, "high": hi, "low": lo, "close": cl, "spread_bps": spread})
    return {"source_id": source_id, "symbol": symbol, "interval_seconds": interval, "bars": bars}


def validate_program(program):
    if not isinstance(program, dict) or set(program) != {"operator", "conditions", "side", "hold_bars", "stop_atr"}:
        raise FoundryError("program_schema")
    if program["operator"] not in ("ALL", "ANY", "SEQUENCE") or program["side"] not in ("BUY", "SELL"):
        raise FoundryError("program_operator_or_side")
    if type(program["hold_bars"]) is not int or program["hold_bars"] not in ALLOWED_HORIZONS:
        raise FoundryError("program_hold")
    if program["stop_atr"] not in (1.5, 2.0, 2.5):
        raise FoundryError("program_stop")
    conditions = program["conditions"]
    if not isinstance(conditions, list) or not 2 <= len(conditions) <= 3:
        raise FoundryError("program_condition_count")
    mechanisms = set()
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) != {"feature", "window", "comparison", "threshold"}:
            raise FoundryError("condition_schema")
        name = condition["feature"]
        if name not in ALLOWED_FEATURES or type(condition["window"]) is not int or condition["window"] not in WINDOWS:
            raise FoundryError("condition_feature_or_window")
        if condition["comparison"] not in ("GT", "LT"):
            raise FoundryError("condition_comparison")
        _number(condition["threshold"], "threshold", min_value=-5, max_value=5)
        mechanisms.add(name)
    if len(mechanisms) < 2:
        raise FoundryError("duplicate_mechanism")
    return program


def structure_signature(program):
    validate_program(program)
    # Numeric parameter changes are never counted as a new mechanism.
    features = [(c["feature"], c["comparison"]) for c in program["conditions"]]
    if program["operator"] != "SEQUENCE":
        features = sorted(features)
    return digest({"operator": program["operator"], "side": program["side"], "features": features})


def _feature(bars, i, feature, window):
    if i < max(2 * window, 48):
        return None
    closes = [b["close"] for b in bars[i - 2 * window:i + 1]]
    if feature == "momentum":
        return (closes[-1] / closes[-1 - window] - 1) * 100
    if feature == "mean_deviation":
        recent = closes[-window:]
        mu = sum(recent) / len(recent)
        deviation = sum(abs(x - mu) for x in recent) / len(recent)
        return (closes[-1] - mu) / max(deviation, 1e-10)
    if feature == "range_location":
        recent = bars[i - window:i]
        low = min(b["low"] for b in recent)
        high = max(b["high"] for b in recent)
        return (closes[-1] - low) / max(high - low, 1e-10) - 0.5
    if feature == "volatility_shift":
        changes = [abs(closes[j] / closes[j - 1] - 1)
                   for j in range(1, len(closes))]
        short = sum(changes[-window:]) / window
        long = sum(changes[:-window]) / max(1, len(changes[:-window]))
        return short / max(long, 1e-10) - 1.0
    raise FoundryError("untrusted_feature")


def signal(program, bars, i):
    validate_program(program)
    votes = []
    for pos, condition in enumerate(program["conditions"]):
        # SEQUENCE expresses an ordered market event, not simultaneous EMA votes.
        at = i - 1 if program["operator"] == "SEQUENCE" and pos == 0 else i
        val = _feature(bars, at, condition["feature"], condition["window"])
        if val is None:
            return False
        votes.append(val > condition["threshold"] if condition["comparison"] == "GT"
                     else val < condition["threshold"])
    return all(votes) if program["operator"] in ("ALL", "SEQUENCE") else any(votes)


def _atr(bars, i, window=14):
    if i < window:
        return 0.0
    values = []
    for n in range(i - window + 1, i + 1):
        b, prev = bars[n], bars[n - 1]
        values.append(max(b["high"] - b["low"], abs(b["high"] - prev["close"]),
                          abs(b["low"] - prev["close"])))
    return sum(values) / len(values)


def _evaluate(program, bars, start, end, *, cost_bps=2.0):
    """Conservative delayed-bar research approximation, not a broker simulator."""
    validate_program(program)
    if not (0 <= start < end <= len(bars)):
        raise FoundryError("split_range")
    fee = _number(cost_bps, "cost_bps", min_value=0, max_value=200) / 10000.0
    outcomes = []
    i = max(start, 49)
    direction = 1 if program["side"] == "BUY" else -1
    while i + program["hold_bars"] + 2 < end:
        if not signal(program, bars, i):
            i += 1
            continue
        # A closed bar is usable only when availability precedes the NEXT
        # completed bar. Entry at that next completed close avoids the look-
        # ahead of claiming a fill at the next opening tick.
        entered = i + 1
        if bars[i]["available_at"] > bars[entered]["t"]:
            i += 1
            continue
        base = bars[entered]["close"]
        spread = bars[entered]["spread_bps"] / 20000.0
        entry = base * (1 + direction * spread)
        stop_distance = max(_atr(bars, i) * program["stop_atr"], base * .0001)
        stop = entry - direction * stop_distance
        take = entry + direction * 1.5 * stop_distance
        if min(entry, stop, take) <= 0:
            i += 1
            continue
        end_hold = min(entered + program["hold_bars"], end - 1)
        exit_price = bars[end_hold]["close"]
        exit_index = end_hold
        for j in range(entered + 1, end_hold + 1):
            row = bars[j]
            stopped = row["low"] <= stop if direction == 1 else row["high"] >= stop
            target = row["high"] >= take if direction == 1 else row["low"] <= take
            if stopped:  # adverse ordering when stop and target hit same bar
                exit_price, exit_index = stop, j
                break
            if target:
                exit_price, exit_index = take, j
                break
        exit_spread = bars[exit_index]["spread_bps"] / 20000.0
        exit_net = exit_price * (1 - direction * exit_spread)
        # Commission affects net P&L, not hypothetical stop/target prices.
        # This keeps identical trade paths comparable under different fees.
        commission_fraction = fee * (1 + exit_price / entry)
        pnl = direction * (exit_net - entry) / entry - commission_fraction
        outcomes.append({"decision_index": i, "entry_index": entered,
                         "exit_index": exit_index, "net_return": round(pnl, 10)})
        i = exit_index + 1
    result = [x["net_return"] for x in outcomes]
    return {"trades": len(result), "net_total_return_additive": round(sum(result), 9),
            "mean_net_trade_return": round(sum(result) / len(result), 9) if result else None,
            "worst_trade_return": min(result) if result else None,
            "fills_model": "delayed-next-closed-bar-cost-stress-not-executable",
            "outcomes": outcomes}


def _behavior(program, bars, end):
    return {i for i in range(49, end) if signal(program, bars, i)}


def _overlap(a, b):
    union = len(a | b)
    return len(a & b) / union if union else 1.0


def discover_training_hypotheses(bars, train_end, *, cost_bps=2.0):
    """Propose primitive event hypotheses from training data only.

    This is a bounded discovery heuristic, *not* statistical significance.
    Every tested primitive is counted for future multiple-testing correction.
    """
    if not 60 <= train_end <= len(bars):
        raise FoundryError("train_end_invalid")
    cost = _number(cost_bps, "cost_bps", min_value=0, max_value=200) / 10000.0
    proposals = []
    number_tested = 0
    for feature in ALLOWED_FEATURES:
        thresholds = {
            "momentum": (-0.3, -0.1, 0.1, 0.3),
            "mean_deviation": (-1.0, -0.5, 0.5, 1.0),
            "range_location": (-0.25, -0.1, 0.1, 0.25),
            "volatility_shift": (-0.2, -0.1, 0.1, 0.2),
        }[feature]
        for window in WINDOWS:
            observed = [(_feature(bars, i, feature, window),
                         bars[i + 1]["close"] / bars[i]["close"] - 1)
                        for i in range(49, train_end - 1)]
            for threshold in thresholds:
                comparison = "GT" if threshold > 0 else "LT"
                relevant = [(value, next_return) for value, next_return in observed
                            if value is not None and (value > threshold if comparison == "GT"
                                                      else value < threshold)]
                for side in ("BUY", "SELL"):
                    number_tested += 1
                    if len(relevant) < 4:
                        continue
                    direction = 1 if side == "BUY" else -1
                    # Preliminary conditional excess return, not deployable edge.
                    conditional = sum(direction * change for _, change in relevant) / len(relevant)
                    base = sum(direction * change for _, change in observed) / len(observed)
                    excess = conditional - base - 2 * cost
                    proposals.append({
                        "feature": feature, "window": window,
                        "comparison": comparison, "threshold": threshold,
                        "side": side, "train_support": len(relevant),
                        "train_excess_after_simple_cost": round(excess, 9),
                        "discovery_score": round(excess * math.sqrt(len(relevant)), 9),
                    })
    # Include weak and negative proposals in the audited trial count; only the
    # top positive hypotheses can seed new strategy candidates.
    selected = [p for p in proposals if p["discovery_score"] > 0]
    selected.sort(key=lambda p: (-p["discovery_score"], p["feature"],
                                 p["window"], p["comparison"], p["side"]))
    return {"primitive_hypotheses_tested": number_tested,
            "primitive_hypotheses_with_support": len(proposals),
            "positive_train_hypotheses": len(selected),
            "proposals": selected[:24]}


def generate_program(rng, proposals=None):
    if proposals:
        sides = []
        for side in ("BUY", "SELL"):
            usable = [p for p in proposals if p["side"] == side]
            if len({p["feature"] for p in usable}) >= 2:
                sides.append(side)
        if not sides:
            raise FoundryError("no_two_mechanism_hypotheses")
        side = rng.choice(sides)
        options = [p for p in proposals if p["side"] == side]
        selected = []
        for feature in rng.sample(sorted({p["feature"] for p in options}), 2):
            choices = [p for p in options if p["feature"] == feature]
            selected.append(rng.choice(choices))
        conditions = [{k: p[k] for k in ("feature", "window", "comparison", "threshold")}
                      for p in selected]
        program = {"operator": rng.choice(("ALL", "ANY", "SEQUENCE")),
                   "conditions": conditions, "side": side,
                   "hold_bars": rng.choice(ALLOWED_HORIZONS),
                   "stop_atr": rng.choice((1.5, 2.0, 2.5))}
        return validate_program(program)
    features = rng.sample(ALLOWED_FEATURES, 2)
    conditions = []
    for feature in features:
        threshold = rng.choice({
            "momentum": (-0.3, -0.1, 0.1, 0.3),
            "mean_deviation": (-1.0, -0.5, 0.5, 1.0),
            "range_location": (-0.25, -0.1, 0.1, 0.25),
            "volatility_shift": (-0.2, -0.1, 0.1, 0.2),
        }[feature])
        conditions.append({"feature": feature, "window": rng.choice(WINDOWS),
                           "comparison": "GT" if threshold > 0 else "LT",
                           "threshold": threshold})
    program = {"operator": rng.choice(("ALL", "ANY", "SEQUENCE")), "conditions": conditions,
               "side": rng.choice(("BUY", "SELL")), "hold_bars": rng.choice(ALLOWED_HORIZONS),
               "stop_atr": rng.choice((1.5, 2.0, 2.5))}
    return validate_program(program)


def invent(payload, *, seed=0, max_trials=32, cost_bps=2.0):
    dataset = validate_dataset(payload)
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise FoundryError("seed_invalid")
    if type(max_trials) is not int or not 1 <= max_trials <= MAX_TRIALS:
        raise FoundryError("trial_budget_invalid")
    _number(cost_bps, "cost_bps", min_value=0, max_value=200)
    rng = random.Random(seed)
    bars = dataset["bars"]
    split = int(len(bars) * .65)
    discovery = discover_training_hypotheses(bars, split, cost_bps=cost_bps)
    proposals = discovery["proposals"]
    if not proposals or not any(
        len({p["feature"] for p in proposals if p["side"] == side}) >= 2
        for side in ("BUY", "SELL")
    ):
        raise FoundryError("no_valid_training_hypotheses")
    structures = set()
    behaviors = []
    trials = []
    births = []
    for trial_number in range(1, max_trials + 1):
        p = generate_program(rng, proposals)
        sig = structure_signature(p)
        trial = {"trial": trial_number, "structure_signature": sig}
        if sig in structures:
            trial["state"] = "REJECTED_DUPLICATE_STRUCTURE"
            trials.append(trial)
            continue
        structures.add(sig)
        signals = _behavior(p, bars, split)
        if len(signals) < MIN_TRAIN_EVENTS:
            trial["state"] = "REJECTED_INACTIVE"
            trials.append(trial)
            continue
        greatest_overlap = max((_overlap(signals, prior) for prior in behaviors), default=0.0)
        if greatest_overlap >= MAX_BEHAVIOR_OVERLAP:
            trial["state"] = "REJECTED_DUPLICATE_BEHAVIOR"
            trials.append(trial)
            continue
        behaviors.append(signals)
        train = _evaluate(p, bars, 0, split, cost_bps=cost_bps)
        holdout = _evaluate(p, bars, split, len(bars), cost_bps=cost_bps)
        birth_id = digest({"dataset": digest(dataset), "program": p})[:24]
        cert = {
            "strategy_id": "MTF-" + birth_id,
            "birth_at": bars[-1]["t"],
            "generator_version": SCHEMA,
            "grammar_version": "bounded-typed-ast-v1",
            "source_id": dataset["source_id"],
            "data_digest": digest(dataset),
            "hypothesis": "Conditional " + p["operator"] + " response to " +
                          " + ".join(c["feature"] for c in p["conditions"]),
            "discovery_mode": "training-only-conditional-event-synthesis",
            "program": p,
            "ast_hash": digest(p),
            "structure_signature": sig,
            "novelty_score": round(1.0 - greatest_overlap, 6),
            "training_signals": len(signals),
            "train": {k: v for k, v in train.items() if k != "outcomes"},
            "holdout": {k: v for k, v in holdout.items() if k != "outcomes"},
            "trial_number": trial_number,
            "state": "RESEARCH_ONLY_UNPROVEN",
            "broker_eligible": False,
            "execution": "disabled",
            "orders": 0,
        }
        cert["receipt_sha256"] = digest(cert)
        births.append(cert)
        trial.update({"state": "BORN_RESEARCH_ONLY", "strategy_id": cert["strategy_id"]})
        trials.append(trial)
    result = {
        "schema": SCHEMA, "mode": "RESEARCH_ONLY", "execution": "disabled",
        "orders": 0, "public_signals": 0,
        "cost_bps_per_side": float(cost_bps), "seed": seed,
        "max_trials": max_trials, "trials_executed": len(trials),
        "dataset_digest": digest(dataset), "dataset_source_id": dataset["source_id"],
        "symbol": dataset["symbol"], "interval_seconds": dataset["interval_seconds"],
        "split": {"train_end_exclusive": split, "holdout_start_inclusive": split,
                  "holdout_end_exclusive": len(bars)},
        "training_discovery": {k: v for k, v in discovery.items() if k != "proposals"},
        "multiple_testing_gate": {
            "status": "NOT_STATISTICALLY_VALIDATED",
            "primitive_hypotheses_tested": discovery["primitive_hypotheses_tested"],
            "candidate_trials_attempted": len(trials),
            "total_search_attempts": discovery["primitive_hypotheses_tested"] + len(trials),
            "holdout_candidates_inspected": len(births),
            "multiplicity_adjusted_evidence": False,
            "eligible_for_broker_or_public_signals": False,
            "next_evidence": ["independent untouched time-period/asset test",
                              "purged walk-forward and dependency-aware significance",
                              "verified execution-cost, slippage and drawdown stress"],
        },
        "trial_ledger": trials, "birth_certificates": births,
        "limitations": ["not a venue/broker backtest", "no proof of profitability",
                        "coarse OHLC ambiguous fills", "selection bias remains possible",
                        "holdout results are research only",
                        "many tested hypotheses can produce misleading positive results"],
    }
    result["report_sha256"] = digest(result)
    return result


def _read_private_input(path):
    if path.is_symlink() or not path.is_file():
        raise FoundryError("input_not_regular")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise FoundryError("input_too_large")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise FoundryError("input_json_invalid") from exc


def write_private(result, target):
    target = Path(target)
    parent = target.parent
    if (parent.is_symlink() or not parent.is_dir() or
            stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise FoundryError("private_dir_required_0700")
    if target.is_symlink():
        raise FoundryError("symlink_target_rejected")
    if target.exists() and not target.is_file():
        raise FoundryError("target_not_file")
    data = canonical(result).encode("utf-8") + b"\n"
    handle = tempfile.NamedTemporaryFile(prefix=".foundry-", dir=parent, delete=False)
    tmp = Path(handle.name)
    try:
        os.chmod(tmp, 0o600)
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def _validate_report_checksum(report):
    if (not isinstance(report, dict) or
            report.get("schema") != SCHEMA or
            report.get("execution") != "disabled" or
            report.get("orders") != 0 or
            report.get("public_signals") != 0 or
            report.get("mode") != "RESEARCH_ONLY"):
        raise FoundryError("registry_report_mode_invalid")
    supplied = report.get("report_sha256")
    if not isinstance(supplied, str) or supplied != digest(
            {k: v for k, v in report.items() if k != "report_sha256"}):
        raise FoundryError("registry_report_digest_invalid")


def _read_and_verify_registry(raw):
    previous = "0" * 64
    records = []
    if raw and not raw.endswith(b"\n"):
        raise FoundryError("registry_partial_record")
    for line in raw.splitlines():
        try:
            record = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise FoundryError("registry_invalid_json") from exc
        if (not isinstance(record, dict) or
                set(record) != {"sequence", "previous_sha256", "report", "entry_sha256"} or
                record["sequence"] != len(records) + 1 or
                record["previous_sha256"] != previous):
            raise FoundryError("registry_chain_invalid")
        _validate_report_checksum(record["report"])
        expected = digest({k: v for k, v in record.items() if k != "entry_sha256"})
        if record["entry_sha256"] != expected:
            raise FoundryError("registry_entry_digest_invalid")
        previous = expected
        records.append(record)
    return records


def append_private_registry(report, target):
    """Bounded full-report hash-chain, locked across processes, idempotent.

    SHA-256 detects accidental/unauthorized mutation relative to trusted
    checkpoints; it is NOT a signature against a writer who can rewrite all
    chain entries. An independent off-host checkpoint is still required.
    """
    _validate_report_checksum(report)
    target = Path(target)
    parent = target.parent
    if (parent.is_symlink() or not parent.is_dir() or
            stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise FoundryError("registry_private_dir_required")
    if target.is_symlink():
        raise FoundryError("registry_symlink_rejected")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | nofollow
    fd = os.open(target, flags, 0o600)
    try:
        metadata = os.fstat(fd)
        if (not stat.S_ISREG(metadata.st_mode) or
                stat.S_IMODE(metadata.st_mode) != 0o600 or
                metadata.st_nlink != 1 or metadata.st_uid != os.geteuid()):
            raise FoundryError("registry_file_permissions_invalid")
        with os.fdopen(fd, "r+b", buffering=0) as handle:
            fd = -1
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            raw = handle.read(MAX_REGISTRY_BYTES + 1)
            if len(raw) > MAX_REGISTRY_BYTES:
                raise FoundryError("registry_capacity_exceeded")
            records = _read_and_verify_registry(raw)
            for existing in records:
                if existing["report"]["report_sha256"] == report["report_sha256"]:
                    return {"written": False, "sequence": existing["sequence"],
                            "entry_sha256": existing["entry_sha256"]}
            if len(records) >= MAX_REGISTRY_ROWS:
                raise FoundryError("registry_record_budget_exceeded")
            entry = {"sequence": len(records) + 1,
                     "previous_sha256": records[-1]["entry_sha256"] if records else "0" * 64,
                     "report": report}
            entry["entry_sha256"] = digest(entry)
            line = canonical(entry).encode("utf-8") + b"\n"
            if len(raw) + len(line) > MAX_REGISTRY_BYTES:
                raise FoundryError("registry_capacity_exceeded")
            handle.seek(0, os.SEEK_END)
            written = handle.write(line)
            if written != len(line):
                raise FoundryError("registry_partial_write")
            os.fsync(handle.fileno())
            return {"written": True, "sequence": entry["sequence"],
                    "entry_sha256": entry["entry_sha256"]}
    finally:
        if fd >= 0:
            os.close(fd)


def verify_private_registry(target):
    target = Path(target)
    if target.is_symlink() or not target.is_file():
        raise FoundryError("registry_missing_or_symlink")
    parent = target.parent
    if (parent.is_symlink() or stat.S_IMODE(parent.stat().st_mode) != 0o700 or
            stat.S_IMODE(target.stat().st_mode) != 0o600):
        raise FoundryError("registry_permissions_invalid")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(target, os.O_RDONLY | nofollow)
    with os.fdopen(fd, "rb") as handle:
        metadata = os.fstat(handle.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or
                metadata.st_uid != os.geteuid() or
                stat.S_IMODE(metadata.st_mode) != 0o600):
            raise FoundryError("registry_file_permissions_invalid")
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        raw = handle.read(MAX_REGISTRY_BYTES + 1)
    if len(raw) > MAX_REGISTRY_BYTES:
        raise FoundryError("registry_capacity_exceeded")
    rows = _read_and_verify_registry(raw)
    return {"records": len(rows), "last_entry_sha256": rows[-1]["entry_sha256"] if rows else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline research-only MojTrade strategy invention")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--trials", type=int, default=32)
    parser.add_argument("--cost-bps", type=float, default=2.0)
    parser.add_argument("--registry", type=Path, help="Private JSONL evidence history (default: output directory)")
    args = parser.parse_args(argv)
    result = invent(_read_private_input(args.input), seed=args.seed,
                    max_trials=args.trials, cost_bps=args.cost_bps)
    registry = args.registry or args.output.parent / "foundry-registry.jsonl"
    if registry.resolve() == args.output.resolve():
        raise FoundryError("registry_cannot_equal_report")
    receipt = append_private_registry(result, registry)
    write_private(result, args.output)
    print("MOJTRADE_FOUNDRY_RESEARCH_SAVED")
    print("MOJTRADE_FOUNDRY_CANDIDATES=" + str(len(result["birth_certificates"])))
    print("MOJTRADE_FOUNDRY_ORDERS=0")
    print("MOJTRADE_FOUNDRY_REGISTRY_SEQUENCE=" + str(receipt["sequence"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

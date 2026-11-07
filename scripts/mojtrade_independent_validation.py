#!/usr/bin/env python3
"""One-shot, offline out-of-sample diagnostics for frozen Foundry programs.

No training on the unseen interval, no broker, and no claim that OHLC backtests
or conservative iid bounds establish profitability. An append-only ledger locks
one research report to its first unseen-dataset digest to expose holdout reuse.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import mojtrade_strategy_foundry as foundry


SCHEMA = "mojtrade.independent-oos.v1"
MIN_UNSEEN_BARS = 300
MIN_TRADES = 30
LEAKAGE_WINDOW_BARS = 32
MAX_LEDGER_BYTES = 8_000_000
MAX_LEDGER_ROWS = 128


class ValidationReject(ValueError):
    """The first untouched OOS verification boundary was violated."""


def _extract(value):
    if isinstance(value, dict) and set(value) == {"dataset", "manifest"}:
        manifest = value["manifest"]
        if (not isinstance(manifest, dict) or manifest.get("evidence_status") != "UNVERIFIED_LOCAL_EXPORT" or
                manifest.get("normalized_dataset_sha256") != foundry.digest(
                    foundry.validate_dataset(value["dataset"])) or
                manifest.get("broker_or_venue_authenticated") is not False):
            raise ValidationReject("csv_manifest_invalid_or_untrusted")
        return foundry.validate_dataset(value["dataset"])
    return foundry.validate_dataset(value)


def _verified_report(report, train):
    try:
        foundry._validate_report_checksum(report)
    except foundry.FoundryError as exc:
        raise ValidationReject("foundry_report_integrity:" + str(exc)) from exc
    if (report.get("dataset_digest") != foundry.digest(train) or
            report.get("dataset_source_id") != train["source_id"] or
            report.get("symbol") != train["symbol"] or
            report.get("interval_seconds") != train["interval_seconds"] or
            not isinstance(report.get("multiple_testing_gate"), dict) or
            report["multiple_testing_gate"].get("status") != "NOT_STATISTICALLY_VALIDATED" or
            report["multiple_testing_gate"].get("eligible_for_broker_or_public_signals") is not False):
        raise ValidationReject("training_dataset_or_statistical_gate_mismatch")
    certs = report.get("birth_certificates")
    if not isinstance(certs, list) or len(certs) > foundry.MAX_TRIALS:
        raise ValidationReject("candidate_count_invalid")
    gate = report["multiple_testing_gate"]
    attempts = gate.get("candidate_trials_attempted")
    primitives = gate.get("primitive_hypotheses_tested")
    if (type(attempts) is not int or type(primitives) is not int or
            attempts < len(certs) or primitives < 0 or
            attempts != report.get("trials_executed") or
            not isinstance(report.get("trial_ledger"), list) or
            attempts != len(report["trial_ledger"]) or
            gate.get("total_search_attempts") != attempts + primitives or
            gate.get("holdout_candidates_inspected") != len(certs)):
        raise ValidationReject("candidate_search_accounting_inconsistent")
    identities = set()
    for cert in certs:
        if (not isinstance(cert, dict) or cert.get("state") != "RESEARCH_ONLY_UNPROVEN" or
                cert.get("broker_eligible") is not False or
                cert.get("execution") != "disabled" or cert.get("orders") != 0 or
                cert.get("generator_version") != foundry.SCHEMA or
                cert.get("source_id") != train["source_id"] or
                cert.get("data_digest") != report["dataset_digest"] or
                cert.get("receipt_sha256") != foundry.digest(
                    {k: v for k, v in cert.items() if k != "receipt_sha256"})):
            raise ValidationReject("candidate_provenance_invalid")
        foundry.validate_program(cert["program"])
        if (cert.get("ast_hash") != foundry.digest(cert["program"]) or
                cert.get("strategy_id") != "MTF-" + foundry.digest({
                    "dataset": report["dataset_digest"], "program": cert["program"]})[:24]):
            raise ValidationReject("candidate_identity_inconsistent")
        if cert["strategy_id"] in identities:
            raise ValidationReject("duplicate_candidate_identity")
        identities.add(cert["strategy_id"])
    return certs


def _test_boundary(train, unseen):
    if (train["symbol"] != unseen["symbol"] or
            train["interval_seconds"] != unseen["interval_seconds"]):
        raise ValidationReject("cross_symbol_or_interval")
    if len(unseen["bars"]) < MIN_UNSEEN_BARS:
        raise ValidationReject("unseen_interval_too_short")
    train_last_seen = datetime.fromisoformat(train["bars"][-1]["available_at"])
    first_unseen = datetime.fromisoformat(unseen["bars"][0]["t"])
    gap = (first_unseen - train_last_seen).total_seconds()
    # The maximum programme holding period is 10 closed bars; purge it before
    # the fully untouched verification period so labelled events cannot cross.
    if gap <= 10 * train["interval_seconds"]:
        raise ValidationReject("unseen_overlap_or_embargo_violation")
    if foundry.digest(train) == foundry.digest(unseen):
        raise ValidationReject("reused_training_dataset")
    # Re-dating training candles must not manufacture an "independent" period.
    # A matching 32-candle OHLC/spread sequence is treated as possible leakage,
    # independent of source labels or timestamps. This is a conservative guard,
    # not verification of the data provider's identity or provenance.
    def windows(rows):
        prices = [tuple(row[key] for key in
                        ("open", "high", "low", "close", "spread_bps"))
                  for row in rows]
        for i in range(len(prices) - LEAKAGE_WINDOW_BARS + 1):
            yield foundry.digest(prices[i:i + LEAKAGE_WINDOW_BARS])

    training_patterns = set(windows(train["bars"]))
    if any(pattern in training_patterns for pattern in windows(unseen["bars"])):
        raise ValidationReject("suspected_replayed_training_candles")


def _cumulative_drawdown(returns):
    running = peak = worst = 0.0
    for value in returns:
        running += value
        peak = max(peak, running)
        worst = max(worst, peak - running)
    return round(worst, 10)


def _hoeffding_one_sided_bound(wins, count):
    # A DIAGNOSTIC under an unverified independent-Bernoulli null, not a
    # calibrated trading p-value for overlapping/serially dependent returns.
    excess = max(0.0, wins - count / 2)
    return math.exp(-2 * excess * excess / count) if count else 1.0


def assess(report, training_data, unseen_data):
    train, unseen = _extract(training_data), _extract(unseen_data)
    certs = _verified_report(report, train)
    _test_boundary(train, unseen)
    raw_tests = report["multiple_testing_gate"].get("total_search_attempts")
    if type(raw_tests) is not int or not len(certs) <= raw_tests <= 10_000:
        raise ValidationReject("familywise_test_count_invalid")
    base_cost = report["cost_bps_per_side"]
    if type(base_cost) not in (int, float) or not math.isfinite(base_cost) or base_cost < 0:
        raise ValidationReject("cost_invalid")
    conservative_cost = min(200.0, max(10.0, base_cost * 3))
    harsh_cost = min(200.0, max(25.0, base_cost * 5))
    bars = unseen["bars"]
    chunk = len(bars) // 3
    segments = [bars[:chunk], bars[chunk:2 * chunk], bars[2 * chunk:]]
    scored = []
    for cert in certs:
        program = cert["program"]
        base = foundry._evaluate(program, bars, 0, len(bars), cost_bps=base_cost)
        stress = foundry._evaluate(program, bars, 0, len(bars), cost_bps=conservative_cost)
        extreme = foundry._evaluate(program, bars, 0, len(bars), cost_bps=harsh_cost)
        outcomes = [x["net_return"] for x in base["outcomes"]]
        count = len(outcomes)
        wins = sum(x > 0 for x in outcomes)
        bound = _hoeffding_one_sided_bound(wins, count)
        adjusted = min(1.0, bound * raw_tests)
        segment_returns = [foundry._evaluate(program, seg, 0, len(seg),
                                           cost_bps=base_cost)["net_total_return_additive"]
                           for seg in segments]
        if count < MIN_TRADES:
            grade = "INSUFFICIENT_UNSEEN_TRADES"
        elif (stress["mean_net_trade_return"] is None or
              stress["mean_net_trade_return"] <= 0 or
              extreme["mean_net_trade_return"] is None or
              extreme["mean_net_trade_return"] <= 0 or
              sum(x > 0 for x in segment_returns) < 2):
            grade = "COST_OR_TIME_REGIME_FRAGILE"
        elif adjusted > 0.01:
            grade = "MULTIPLICITY_NOT_CLEARED"
        else:
            grade = "DIAGNOSTIC_POSITIVE_BUT_UNVERIFIED"
        scored.append({
            "strategy_id": cert["strategy_id"], "state": grade,
            "unseen_trade_count": count, "unseen_wins": wins,
            "unseen_mean_net_return": base["mean_net_trade_return"],
            "unseen_max_additive_drawdown": _cumulative_drawdown(outcomes),
            "cost_stress_bps_per_side": conservative_cost,
            "cost_stress_mean_net_return": stress["mean_net_trade_return"],
            "harsh_cost_bps_per_side": harsh_cost,
            "harsh_cost_mean_net_return": extreme["mean_net_trade_return"],
            "three_unseen_segment_net_returns": segment_returns,
            "iid_sign_bound_diagnostic": round(bound, 12),
            "familywise_bonferroni_bound_diagnostic": round(adjusted, 12),
            "broker_eligible": False,
        })
    receipt = {
        "schema": SCHEMA, "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "INDEPENDENT_DIAGNOSTICS_NOT_TRADING_VALIDATION",
        "report_sha256": report["report_sha256"],
        "training_dataset_sha256": foundry.digest(train),
        "untouched_dataset_sha256": foundry.digest(unseen),
        "symbol": train["symbol"], "interval_seconds": train["interval_seconds"],
        "purge_embargo_bars": 10, "unseen_bars": len(bars),
        "familywise_hypotheses_count": raw_tests,
        "zero_trade_baseline": 0,
        "raw_buy_hold_price_change": round(bars[-1]["close"] / bars[0]["close"] - 1, 10),
        "candidates": scored, "public_signals": 0, "real_orders": 0,
        "broker_eligible": False,
        "limitations": ["underlying data/CSV source not authenticated",
                        "OHLC delayed-fill model not venue execution",
                        "iid sign bound not calibrated for overlapping dependent returns",
                        "one held-out period is not a prospective forward trial",
                        "Bonferroni diagnostic does not eliminate strategy-search bias",
                        "no economic profitability demonstrated"],
    }
    receipt["receipt_sha256"] = foundry.digest(receipt)
    return receipt


def _read_journal(raw):
    if raw and not raw.endswith(b"\n"):
        raise ValidationReject("journal_partial_record")
    previous, rows = "0" * 64, []
    for line in raw.splitlines():
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise ValidationReject("journal_invalid_json") from exc
        if (not isinstance(record, dict) or set(record) !=
                {"sequence", "previous_sha256", "receipt", "entry_sha256"} or
                record["sequence"] != len(rows) + 1 or record["previous_sha256"] != previous):
            raise ValidationReject("journal_chain_invalid")
        receipt = record["receipt"]
        if (not isinstance(receipt, dict) or receipt.get("receipt_sha256") !=
                foundry.digest({k: v for k, v in receipt.items() if k != "receipt_sha256"}) or
                record["entry_sha256"] != foundry.digest(
                    {k: v for k, v in record.items() if k != "entry_sha256"})):
            raise ValidationReject("journal_checksum_invalid")
        previous = record["entry_sha256"]
        rows.append(record)
    return rows


def validate_once(report, training_data, unseen_data, ledger):
    """Freeze the *first* unseen data digest for each Foundry report SHA."""
    receipt = assess(report, training_data, unseen_data)
    path = Path(ledger)
    parent = path.parent
    if (parent.is_symlink() or not parent.is_dir() or
            stat.S_IMODE(parent.stat().st_mode) != 0o700 or path.is_symlink()):
        raise ValidationReject("private_ledger_directory_required")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode) or stat.S_IMODE(meta.st_mode) != 0o600 or
                meta.st_uid != os.geteuid() or meta.st_nlink != 1):
            raise ValidationReject("ledger_permissions_invalid")
        with os.fdopen(fd, "r+b", buffering=0) as handle:
            fd = -1
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            raw = handle.read(MAX_LEDGER_BYTES + 1)
            if len(raw) > MAX_LEDGER_BYTES:
                raise ValidationReject("ledger_over_capacity")
            rows = _read_journal(raw)
            for row in rows:
                prior = row["receipt"]
                if prior["report_sha256"] == receipt["report_sha256"]:
                    if prior["receipt_sha256"] != receipt["receipt_sha256"]:
                        raise ValidationReject("holdout_reuse_different_dataset_prohibited")
                    return {"receipt": prior, "ledger_sequence": row["sequence"],
                            "ledger_entry_sha256": row["entry_sha256"]}
            if len(rows) >= MAX_LEDGER_ROWS:
                raise ValidationReject("ledger_row_budget_exhausted")
            record = {"sequence": len(rows) + 1,
                      "previous_sha256": rows[-1]["entry_sha256"] if rows else "0" * 64,
                      "receipt": receipt}
            record["entry_sha256"] = foundry.digest(record)
            encoded = (foundry.canonical(record) + "\n").encode()
            if len(raw) + len(encoded) > MAX_LEDGER_BYTES:
                raise ValidationReject("ledger_over_capacity")
            handle.seek(0, os.SEEK_END)
            if handle.write(encoded) != len(encoded):
                raise ValidationReject("ledger_partial_write")
            os.fsync(handle.fileno())
            return {"receipt": receipt, "ledger_sequence": record["sequence"],
                    "ledger_entry_sha256": record["entry_sha256"]}
    finally:
        if fd >= 0:
            os.close(fd)


def _read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 3_000_000:
        raise ValidationReject("unsafe_json_source")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Locked independent out-of-sample research diagnostics")
    parser.add_argument("--foundry-report", required=True, type=Path)
    parser.add_argument("--training-data", required=True, type=Path)
    parser.add_argument("--unseen-data", required=True, type=Path)
    parser.add_argument("--private-ledger", required=True, type=Path)
    args = parser.parse_args(argv)
    result = validate_once(_read_json(args.foundry_report), _read_json(args.training_data),
                           _read_json(args.unseen_data), args.private_ledger)
    print(json.dumps({"status": result["receipt"]["status"],
                      "ledger_sequence": result["ledger_sequence"],
                      "evaluated_candidates": len(result["receipt"]["candidates"]),
                      "real_orders": 0, "public_signals": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

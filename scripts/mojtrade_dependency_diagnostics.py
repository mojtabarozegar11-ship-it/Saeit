#!/usr/bin/env python3
"""Deterministic stationary-block sensitivity on a *frozen* independent OOS.

All strategies share each block-resampled time index. The diagnostic does not
authorize trading, broker connectivity or public signal distribution.
"""

from __future__ import annotations

import argparse
import json
import random

import mojtrade_independent_validation as oos


SCHEMA = "mojtrade.dependency-diagnostics.v1"
BLOCK_LENGTHS = (8, 16, 32)
RESAMPLES = 256


class DependencyReject(ValueError):
    """The frozen OOS evidence or dependent diagnostic is inconsistent."""


def _realized_bar_series(outcomes, n_bars):
    series = [0.0] * n_bars
    previous_exit = -1
    for outcome in outcomes:
        if (not isinstance(outcome, dict) or
                type(outcome.get("exit_index")) is not int or
                not previous_exit < outcome["exit_index"] < n_bars or
                type(outcome.get("net_return")) not in (int, float)):
            raise DependencyReject("invalid_or_overlapping_simulated_exit")
        series[outcome["exit_index"]] += outcome["net_return"]
        previous_exit = outcome["exit_index"]
    return series


def _stationary_path(rng, n, mean_block_length):
    """Geometric-length circular blocks, with stationary uniform starting index."""
    if n <= 0 or mean_block_length < 1:
        raise DependencyReject("invalid_stationary_resample_configuration")
    pos = rng.randrange(n)
    result = []
    for i in range(n):
        if i:
            pos = rng.randrange(n) if rng.random() < 1.0 / mean_block_length else (pos + 1) % n
        result.append(pos)
    return result


def _max_family_null(series, seed_material):
    """One-sided max-centered-null diagnostics for all frozen OOS candidates.

    Every candidate is sampled on the SAME time indices in each replication,
    preserving observed cross-candidate co-movement within sampled blocks.
    This approximates the null only under unverified weak-stationarity and
    sufficiently short-range dependence assumptions.
    """
    if not series:
        return {}
    n = len(series[0])
    if n < oos.MIN_UNSEEN_BARS or any(len(row) != n for row in series):
        raise DependencyReject("unequal_or_short_realized_series")
    observed = [sum(row) / n for row in series]
    centered = [[value - mean for value in row] for row, mean in zip(series, observed)]
    output = {}
    for block in BLOCK_LENGTHS:
        seed = int(oos.foundry.digest({"schema": SCHEMA, "frozen": seed_material,
                                      "mean_block_length": block})[:16], 16)
        rng = random.Random(seed)
        maxima = []
        for _ in range(RESAMPLES):
            path = _stationary_path(rng, n, block)
            maxima.append(max(sum(row[t] for t in path) / n for row in centered))
        output[str(block)] = [round((1 + sum(x >= observed[j] for x in maxima)) /
                                    (RESAMPLES + 1), 7)
                              for j in range(len(series))]
    return output


def audit(report, training_data, unseen_data, frozen_oos_receipt):
    """Inspect dependency robustness without altering the frozen OOS receipt."""
    expected = oos.assess(report, training_data, unseen_data)
    if not isinstance(frozen_oos_receipt, dict) or frozen_oos_receipt != expected:
        raise DependencyReject("frozen_oos_receipt_not_identical")
    unseen = oos._extract(unseen_data)
    bars = unseen["bars"]
    candidates = report["birth_certificates"]
    realized = [_realized_bar_series(oos.foundry._evaluate(
        cert["program"], bars, 0, len(bars),
        cost_bps=report["cost_bps_per_side"])["outcomes"], len(bars))
        for cert in candidates]
    by_block = _max_family_null(realized, expected["receipt_sha256"])
    rows = []
    for j, cert in enumerate(candidates):
        p_by_block = {block: values[j] for block, values in by_block.items()}
        rows.append({"strategy_id": cert["strategy_id"],
                     "realized_simulated_exit_bars": sum(v != 0 for v in realized[j]),
                     "mean_realized_bar_additive_return": round(sum(realized[j]) / len(bars), 12),
                     "max_family_one_sided_p_by_block_DIAGNOSTIC_ONLY": p_by_block,
                     "worst_block_sensitivity_DIAGNOSTIC_ONLY": max(p_by_block.values()),
                     "broker_eligible": False})
    receipt = {
        "schema": SCHEMA, "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "DEPENDENCE_SENSITIVITY_NOT_STATISTICAL_VALIDATION",
        "frozen_oos_receipt_sha256": expected["receipt_sha256"],
        "report_sha256": report["report_sha256"],
        "unseen_dataset_sha256": expected["untouched_dataset_sha256"],
        "candidate_family": "all_pre_registered_Foundry_births_on_this_unseen_period",
        "family_size": len(candidates),
        "other_prior_search_attempts": (expected["familywise_hypotheses_count"] - len(candidates)),
        "resampler": "stationary_geometric_circular_blocks_shared_across_candidates",
        "fixed_block_lengths_bars": list(BLOCK_LENGTHS),
        "fixed_resamples_per_block": RESAMPLES,
        "null": "each_candidate_additive_bar_return_mean_centered_at_zero",
        "realization": "simulated_trade_net_return_booked_only_on_exit_bar",
        "candidates": rows, "broker_eligible": False,
        "real_orders": 0, "public_signals": 0,
        "limitations": [
            "requires independent untouched data, which local inputs cannot authenticate",
            "assumes weak stationarity and sufficiently short memory; neither verified",
            "realized exit-only OHLC returns are not mark-to-market portfolio equity",
            "finite resamples and fixed block choices are sensitivity diagnostics",
            "max family covers frozen OOS candidates, not all adaptive research choices",
            "no calibrated trading p-values or future-profit evidence",
        ],
    }
    receipt["receipt_sha256"] = oos.foundry.digest(receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline frozen OOS dependency sensitivity")
    parser.add_argument("--foundry-report", required=True)
    parser.add_argument("--training-data", required=True)
    parser.add_argument("--unseen-data", required=True)
    parser.add_argument("--private-ledger", required=True)
    args = parser.parse_args(argv)
    report, train, unseen = (oos._read_json(item) for item in
                           (args.foundry_report, args.training_data, args.unseen_data))
    freeze = oos.validate_once(report, train, unseen, args.private_ledger)
    result = audit(report, train, unseen, freeze["receipt"])
    print(json.dumps({"status": result["status"], "receipt_sha256": result["receipt_sha256"],
                      "candidate_count": result["family_size"],
                      "block_lengths_bars": result["fixed_block_lengths_bars"],
                      "real_orders": 0, "public_signals": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

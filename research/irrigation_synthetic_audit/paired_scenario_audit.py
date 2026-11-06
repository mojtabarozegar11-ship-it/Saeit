#!/usr/bin/env python3
"""Independent post-processing audit of the synthetic irrigation scenario tables.

This script checks archived OUTPUTS, not the weather generator, sensor model,
crop performance, real-world savings, or the field validity of any controller.
It uses only the Python standard library and needs no account or network access.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


FIELDS = (
    "cohort", "seed", "climate_class", "bias_vwc",
    "et_forecast_multiplier", "forecast_case", "policy",
    "gross_water_m3", "irrigation_events", "q_positive_plot_days",
    "below_98_plot_days", "drainage_sum_mm",
)
POLICIES = {
    "C": {"integrated", "v2", "v3"},
    "R1": {"integrated", "integrated_forecast_ET", "v2", "v3"},
}
WEIGHTS = (0, 1, 2, 5, 10, 20, 50, 100)
TOL = 1e-8
EXPECTED = {
    "C": {
        "mean_delta_water": 36.068956, "mean_delta_q": -6.892593,
        "q_lower_tied_higher": [214, 311, 15], "higher_water": 383,
        "v3_dominates": 65, "v2_dominates": 229, "both_tied": 89,
        "q_better_water_worse": 157, "crossing_median": 2.841907,
        "lambda_10": [196, 255, 89, -32.856970],
    },
    "R1": {
        "mean_delta_water": 30.575281, "mean_delta_q": -7.470370,
        "q_lower_tied_higher": [212, 326, 2], "higher_water": 401,
        "v3_dominates": 43, "v2_dominates": 232, "both_tied": 94,
        "q_better_water_worse": 171, "crossing_median": 1.372369,
        "lambda_10": [193, 253, 94, -44.128422],
    },
}


class AuditError(ValueError):
    """Input or published-checkpoint discrepancy."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def numeric(text: str, label: str) -> float:
    try:
        value = float(text)
    except (TypeError, ValueError) as exc:
        raise AuditError(f"Invalid numeric {label}: {text!r}") from exc
    require(math.isfinite(value), f"Nonfinite {label}: {text!r}")
    return value


def load_records(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None, f"Missing CSV header: {path}")
        require(set(FIELDS).issubset(reader.fieldnames),
                f"Missing columns in {path}: {sorted(set(FIELDS)-set(reader.fieldnames))}")
        for line, raw in enumerate(reader, start=2):
            require(raw.get("cohort") and raw.get("policy"),
                    f"Missing scenario/policy at {path}:{line}")
            try:
                seed = int(raw["seed"])
                events = int(raw["irrigation_events"])
                q = int(raw["q_positive_plot_days"])
                q98 = int(raw["below_98_plot_days"])
            except (ValueError, TypeError) as exc:
                raise AuditError(f"Invalid count/seed at {path}:{line}") from exc
            water = numeric(raw["gross_water_m3"], f"{path}:{line}:water")
            drainage = numeric(raw["drainage_sum_mm"], f"{path}:{line}:drainage")
            bias = numeric(raw["bias_vwc"], f"{path}:{line}:bias")
            et = numeric(raw["et_forecast_multiplier"], f"{path}:{line}:ET")
            require(0 <= water <= 320 + TOL, f"Water cap exceeded at {path}:{line}")
            require(0 <= events <= 120 and 0 <= q98 <= q <= 120,
                    f"Invalid event or threshold count at {path}:{line}")
            require(drainage >= -TOL, f"Negative drainage at {path}:{line}")
            require(raw["climate_class"] in ("dry", "medium", "wet"),
                    f"Invalid climate class at {path}:{line}")
            require(raw["forecast_case"] in ("perfect", "missing", "falsePositive"),
                    f"Invalid forecast case at {path}:{line}")
            require(any(abs(bias-b) < TOL for b in (-.02, -.01, 0, .01, .02)),
                    f"Unexpected sensor bias at {path}:{line}")
            require(any(abs(et-e) < TOL for e in (.85, 1., 1.15)),
                    f"Unexpected ET factor at {path}:{line}")
            records.append({
                "key": (raw["cohort"], seed, raw["climate_class"],
                        round(bias, 8), round(et, 8), raw["forecast_case"]),
                "policy": raw["policy"], "water": water, "q": q,
                "q98": q98, "events": events, "drainage": drainage,
            })
    return records


def analyze_family(records: list[dict], family: str) -> dict:
    require(family in POLICIES, f"Unknown family {family}")
    policies = POLICIES[family]
    required_rows = 540 * len(policies)
    require(len(records) == required_rows,
            f"{family}: {len(records)} rows; expected {required_rows}")
    matched: dict[tuple, dict[str, dict]] = defaultdict(dict)
    paths: dict[tuple, set[tuple]] = defaultdict(set)
    policy_values: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        key, policy = row["key"], row["policy"]
        require(policy in policies, f"{family}: unexpected policy {policy!r}")
        require(policy not in matched[key], f"{family}: duplicate (key,policy): {key,policy}")
        matched[key][policy] = row
        paths[key[:3]].add(key)
        policy_values[policy].append(row)
    require(len(matched) == 540, f"{family}: expected 540 unique matched keys")
    require(len(paths) == 12, f"{family}: expected 12 distinct climate paths")
    for path, keys in paths.items():
        require(len(keys) == 45, f"{family}: path {path} has {len(keys)} settings; expected 45")
    for key, vals in matched.items():
        require(set(vals) == policies, f"{family}: incomplete policy match for {key}")

    means = {p: {
        "water_m3": statistics.fmean(x["water"] for x in rows),
        "q100_plot_days": statistics.fmean(x["q"] for x in rows),
        "drainage_m3_equivalent": statistics.fmean(x["drainage"] for x in rows),
        "count": len(rows),
    } for p, rows in sorted(policy_values.items())}
    counts = dict(q_lower=0, q_tied=0, q_higher=0, higher_water=0,
                  v3_dominates=0, v2_dominates=0, both_tied=0,
                  q_better_water_worse=0)
    crossed = []
    all_deltas = []
    by_class: dict[str, dict[str, int]] = defaultdict(lambda: dict(v3=0, v2=0, tied=0))
    weights = {w: dict(v3=0, v2=0, tied=0) for w in WEIGHTS}
    for key, values in matched.items():
        v2, v3 = values["v2"], values["v3"]
        dv, dq = v3["water"] - v2["water"], v3["q"] - v2["q"]
        all_deltas.append((dv, dq))
        counts["q_lower" if dq < 0 else "q_higher" if dq > 0 else "q_tied"] += 1
        counts["higher_water"] += dv > TOL
        counts["v3_dominates"] += dv <= TOL and dq <= 0 and (dv < -TOL or dq < 0)
        counts["v2_dominates"] += dv >= -TOL and dq >= 0 and (dv > TOL or dq > 0)
        counts["both_tied"] += abs(dv) <= TOL and dq == 0
        if dq < 0 and dv > TOL:
            counts["q_better_water_worse"] += 1
            crossed.append(dv / -dq)
        for w in WEIGHTS:
            loss_diff = dv + w * dq
            label = "v3" if loss_diff < -TOL else "v2" if loss_diff > TOL else "tied"
            weights[w][label] += 1
            if w == 10:
                by_class[key[2]][label] += 1
    mean_dv = statistics.fmean(x[0] for x in all_deltas)
    mean_dq = statistics.fmean(x[1] for x in all_deltas)
    return {
        "family": family, "record_count": len(records), "matched_keys": len(matched),
        "climate_paths": len(paths), "means": means, "comparisons": counts,
        "mean_delta_water_m3": mean_dv, "mean_delta_q100": mean_dq,
        "mean_loss_crossing_lambda": mean_dv / -mean_dq if mean_dq < 0 else None,
        "case_crossing_lambda_median": statistics.median(crossed),
        "weights": {str(w): {**weights[w], "mean_delta_loss": mean_dv+w*mean_dq}
                    for w in WEIGHTS},
        "lambda_10_by_climate_class": dict(sorted(by_class.items())),
    }


def verify_paper(report: dict) -> None:
    e = EXPECTED[report["family"]]
    c = report["comparisons"]
    require([c["q_lower"], c["q_tied"], c["q_higher"]] == e["q_lower_tied_higher"],
            f"{report['family']}: Q comparison discrepancy")
    for key in ("higher_water", "v3_dominates", "v2_dominates",
                "both_tied", "q_better_water_worse"):
        require(c[key] == e[key], f"{report['family']}: count mismatch: {key}")
    for output, expected in (("mean_delta_water_m3", e["mean_delta_water"]),
                             ("mean_delta_q100", e["mean_delta_q"]),
                             ("case_crossing_lambda_median", e["crossing_median"])):
        require(abs(report[output]-expected) <= 0.0000005,
                f"{report['family']}: manuscript checkpoint mismatch: {output}")
    row = report["weights"]["10"]
    expected = e["lambda_10"]
    require([row["v3"], row["v2"], row["tied"]] == expected[:3],
            f"{report['family']}: lambda=10 preference mismatch")
    require(abs(row["mean_delta_loss"]-expected[3]) <= 0.0000005,
            f"{report['family']}: lambda=10 mean difference mismatch")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-c", type=Path, required=True)
    parser.add_argument("--regime-r1", type=Path, required=True)
    parser.add_argument("--verify-paper", action="store_true",
                        help="Reject output inconsistent with six-decimal manuscript checkpoints")
    args = parser.parse_args()
    try:
        reports = []
        for family, path in (("C", args.cohort_c), ("R1", args.regime_r1)):
            data = analyze_family(load_records(path), family)
            if args.verify_paper:
                verify_paper(data)
            data["source_csv_sha256"] = file_sha256(path)
            reports.append(data)
    except (AuditError, OSError) as error:
        print(f"AUDIT FAILED: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "audit": "synthetic matched-scenario output post-processing",
        "manuscript_numeric_checkpoint": "PASS" if args.verify_paper else "NOT_REQUESTED",
        "limits": "No simulation-generator replay, field validation, yield effect, or real water saving is established.",
        "families": reports,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

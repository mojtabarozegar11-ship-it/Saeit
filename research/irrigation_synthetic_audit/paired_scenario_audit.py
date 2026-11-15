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
# Actual author-owned RegimeR2160 workbook rows use "R-", not "R1-".
FAMILY_COHORT_PREFIX = {"C": "C-", "R1": "R-"}
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


# Values independently cross-checked against the author-held native
# DecisionWeights!H1:P9 worksheet (eight illustrative weights per family).
# This is a SYNTHETIC output-consistency gate, not evidence of field benefit.
EXPECTED_WEIGHT_GRID = {
    "C": {
        0: (20, 383, 137, 36.068955967),
        1: (117, 334, 89, 29.176363375),
        2: (136, 315, 89, 22.283770782),
        5: (161, 290, 89, 1.605993004),
        10: (196, 255, 89, -32.856969959),
        20: (213, 238, 89, -101.782895885),
        50: (217, 234, 89, -308.560673662),
        100: (222, 229, 89, -653.190303292),
    },
    "R1": {
        0: (13, 401, 126, 30.575281425),
        1: (115, 331, 94, 23.104911054),
        2: (144, 302, 94, 15.634540684),
        5: (185, 261, 94, -6.776570427),
        10: (193, 253, 94, -44.128422279),
        20: (204, 242, 94, -118.832125983),
        50: (214, 232, 94, -342.943237094),
        100: (214, 232, 94, -716.461755612),
    },
}


# Exact (cohort ID, seed, class) paths observed in the author-controlled
# native Sheets C and R1 tabs on 2026-11-15. This checks archive identity;
# it DOES NOT authenticate weather inputs, generator correctness or field data.
SOURCE_PATHS = {
    "C": {
        ("C-dry-1", 919, "dry"), ("C-dry-2", 1111, "dry"),
        ("C-dry-3", 1212, "dry"), ("C-dry-4", 1313, "dry"),
        ("C-medium-1", 1919, "medium"), ("C-medium-2", 2111, "medium"),
        ("C-medium-3", 2212, "medium"), ("C-medium-4", 2313, "medium"),
        ("C-wet-1", 2919, "wet"), ("C-wet-2", 3111, "wet"),
        ("C-wet-3", 3212, "wet"), ("C-wet-4", 3313, "wet"),
    },
    "R1": {
        ("R-dry-1", 173, "dry"), ("R-dry-2", 347, "dry"),
        ("R-dry-3", 521, "dry"), ("R-dry-4", 695, "dry"),
        ("R-medium-1", 2173, "medium"), ("R-medium-2", 2347, "medium"),
        ("R-medium-3", 2521, "medium"), ("R-medium-4", 2695, "medium"),
        ("R-wet-1", 4173, "wet"), ("R-wet-2", 4347, "wet"),
        ("R-wet-3", 4521, "wet"), ("R-wet-4", 4695, "wet"),
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
        require(len(reader.fieldnames) == len(set(reader.fieldnames)),
                f"Duplicate CSV header names in {path}")
        require(set(FIELDS).issubset(reader.fieldnames),
                f"Missing columns in {path}: {sorted(set(FIELDS)-set(reader.fieldnames))}")
        for line, raw in enumerate(reader, start=2):
            require(None not in raw, f"Unexpected extra CSV fields at {path}:{line}")
            require(raw.get("cohort") and raw.get("policy"),
                    f"Missing scenario/policy at {path}:{line}")
            try:
                seed = int(raw["seed"])
                events = int(raw["irrigation_events"])
                q = int(raw["q_positive_plot_days"])
                q98 = int(raw["below_98_plot_days"])
            except (ValueError, TypeError) as exc:
                raise AuditError(f"Invalid count/seed at {path}:{line}") from exc
            require(seed >= 0, f"Negative synthetic weather seed at {path}:{line}")
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
        require(key[0].startswith(FAMILY_COHORT_PREFIX[family]),
                f"{family}: cross-family or malformed cohort identifier: {key[0]!r}")
        require(key[0].startswith(f"{FAMILY_COHORT_PREFIX[family]}{key[2]}-"),
                f"{family}: cohort climate class disagrees with climate_class: {key[0]!r}, {key[2]!r}")
        require(policy in policies, f"{family}: unexpected policy {policy!r}")
        require(policy not in matched[key], f"{family}: duplicate (key,policy): {key,policy}")
        matched[key][policy] = row
        paths[key[:3]].add(key)
        policy_values[policy].append(row)
    require(len(matched) == 540, f"{family}: expected 540 unique matched keys")
    require(len(paths) == 12, f"{family}: expected 12 distinct climate paths")
    climate_path_counts = {climate: sum(path[2] == climate for path in paths)
                           for climate in ("dry", "medium", "wet")}
    require(all(count == 4 for count in climate_path_counts.values()),
            f"{family}: unbalanced climate paths: {climate_path_counts}; expected 4 per class")
    expected_grid = {(b, e, forecast) for b in (-.02, -.01, 0., .01, .02)
                     for e in (.85, 1., 1.15)
                     for forecast in ("perfect", "missing", "falsePositive")}
    for path, keys in paths.items():
        require(len(keys) == 45, f"{family}: path {path} has {len(keys)} settings; expected 45")
        observed_grid = {(key[3], key[4], key[5]) for key in keys}
        require(observed_grid == expected_grid,
                f"{family}: path {path} has missing or unexpected factorial settings")
    for key, vals in matched.items():
        require(set(vals) == policies, f"{family}: incomplete policy match for {key}")

    # The source drainage field is in mm. Never label its arithmetic mean as m3.
    means = {p: {
        "water_m3": statistics.fmean(x["water"] for x in rows),
        "q100_plot_days": statistics.fmean(x["q"] for x in rows),
        "drainage_sum_mm": statistics.fmean(x["drainage"] for x in rows),
        "count": len(rows),
    } for p, rows in sorted(policy_values.items())}
    counts = dict(q_lower=0, q_tied=0, q_higher=0, higher_water=0,
                  v3_dominates=0, v2_dominates=0, both_tied=0,
                  q_better_water_worse=0, water_better_q_worse=0)
    crossed = []
    all_deltas = []
    # Supplementary outcomes are modeled events and depths, not measured
    # farm outcomes; keep drainage in millimetres, never invent m3 volume.
    supplementary_fields = {
        "below_98_plot_days": ("q98", "simulated threshold plot-days"),
        "irrigation_events": ("events", "simulated irrigation events"),
        "drainage_sum_mm": ("drainage", "summed depth in mm"),
    }
    supplementary_deltas: dict[str, list[float]] = {
        name: [] for name in supplementary_fields
    }
    supplementary_paths: dict[str, dict[tuple, list[float]]] = {
        name: defaultdict(list) for name in supplementary_fields
    }
    path_deltas: dict[tuple, list[tuple[float, int]]] = defaultdict(list)
    by_class: dict[str, dict[str, int]] = defaultdict(lambda: dict(v3=0, v2=0, tied=0))
    weights = {w: dict(v3=0, v2=0, tied=0) for w in WEIGHTS}
    for key, values in matched.items():
        v2, v3 = values["v2"], values["v3"]
        dv, dq = v3["water"] - v2["water"], v3["q"] - v2["q"]
        all_deltas.append((dv, dq))
        path_deltas[key[:3]].append((dv, dq))
        for name, (field, _unit) in supplementary_fields.items():
            difference = v3[field] - v2[field]
            supplementary_deltas[name].append(difference)
            supplementary_paths[name][key[:3]].append(difference)
        counts["q_lower" if dq < 0 else "q_higher" if dq > 0 else "q_tied"] += 1
        counts["higher_water"] += dv > TOL
        counts["v3_dominates"] += dv <= TOL and dq <= 0 and (dv < -TOL or dq < 0)
        counts["v2_dominates"] += dv >= -TOL and dq >= 0 and (dv > TOL or dq > 0)
        counts["both_tied"] += abs(dv) <= TOL and dq == 0
        if dq < 0 and dv > TOL:
            counts["q_better_water_worse"] += 1
            crossed.append(dv / -dq)
        if dq > 0 and dv < -TOL:
            counts["water_better_q_worse"] += 1
        for w in WEIGHTS:
            loss_diff = dv + w * dq
            label = "v3" if loss_diff < -TOL else "v2" if loss_diff > TOL else "tied"
            weights[w][label] += 1
            if w == 10:
                by_class[key[2]][label] += 1
    pareto_categories = ("v3_dominates", "v2_dominates", "both_tied",
                         "q_better_water_worse", "water_better_q_worse")
    require(sum(counts[name] for name in pareto_categories) == len(matched),
            f"{family}: incomplete Pareto outcome partition")
    climate_class_effects = {}
    for climate in ("dry", "medium", "wet"):
        deltas = [delta for path, values in path_deltas.items()
                  if path[2] == climate for delta in values]
        require(len(deltas) == 180,
                f"{family}: {climate} has {len(deltas)} matched settings, expected 180")
        climate_class_effects[climate] = {
            "matched_keys": len(deltas),
            "climate_paths": 4,
            "mean_delta_water_m3": statistics.fmean(delta[0] for delta in deltas),
            "mean_delta_q100": statistics.fmean(delta[1] for delta in deltas),
        }
    climate_path_effects = [{
        "cohort": path[0], "seed": path[1], "climate_class": path[2],
        "matched_keys": len(deltas),
        "mean_delta_water_m3": statistics.fmean(x[0] for x in deltas),
        "mean_delta_q100": statistics.fmean(x[1] for x in deltas),
    } for path, deltas in sorted(path_deltas.items())]
    mean_dv = statistics.fmean(x[0] for x in all_deltas)
    mean_dq = statistics.fmean(x[1] for x in all_deltas)
    supplementary_results = {}
    for name, values in supplementary_deltas.items():
        path_means = [{
            "cohort": path[0], "seed": path[1], "climate_class": path[2],
            "matched_keys": len(path_values),
            "mean_delta": statistics.fmean(path_values),
        } for path, path_values in sorted(supplementary_paths[name].items())]
        supplementary_results[name] = {
            "unit": supplementary_fields[name][1],
            "direction": "v3 minus v2",
            "matched_keys": len(values),
            "mean_delta": statistics.fmean(values),
            "median_delta": statistics.median(values),
            "range_delta": [min(values), max(values)],
            "by_climate_path": path_means,
            "by_climate_class": {
                climate: {
                    "matched_keys": len(filtered),
                    "mean_delta": statistics.fmean(filtered),
                }
                for climate in ("dry", "medium", "wet")
                for filtered in [[
                    value for path, path_values in supplementary_paths[name].items()
                    if path[2] == climate for value in path_values
                ]]
            },
        }
    # Drop one synthetic climate path at a time as a deterministic
    # sensitivity diagnostic. This is NOT a cluster bootstrap or CI.
    leave_one_path_out = []
    water_total = sum(x[0] for x in all_deltas)
    q_total = sum(x[1] for x in all_deltas)
    for path, deltas in sorted(path_deltas.items()):
        remaining = len(all_deltas) - len(deltas)
        require(remaining == 495, f"{family}: invalid leave-one-path-out count")
        omitted_water = sum(x[0] for x in deltas)
        omitted_q = sum(x[1] for x in deltas)
        leave_one_path_out.append({
            "excluded_path": path[0],
            "excluded_seed": path[1],
            "climate_class": path[2],
            "remaining_matched_keys": remaining,
            "mean_delta_water_m3": (water_total - omitted_water) / remaining,
            "mean_delta_q100": (q_total - omitted_q) / remaining,
        })
    return {
        "family": family, "record_count": len(records), "matched_keys": len(matched),
        "climate_paths": len(paths), "climate_path_effects": climate_path_effects,
        "climate_class_effects": climate_class_effects,
        "supplementary_paired_outcomes": supplementary_results,
        "leave_one_climate_path_out": leave_one_path_out,
        "means": means, "comparisons": counts,
        "mean_delta_water_m3": mean_dv, "mean_delta_q100": mean_dq,
        "median_delta_water_m3": statistics.median(x[0] for x in all_deltas),
        "median_delta_q100": statistics.median(x[1] for x in all_deltas),
        "range_delta_water_m3": [min(x[0] for x in all_deltas),
                                  max(x[0] for x in all_deltas)],
        "range_delta_q100": [min(x[1] for x in all_deltas),
                             max(x[1] for x in all_deltas)],
        "mean_loss_crossing_lambda": mean_dv / -mean_dq if mean_dq < 0 else None,
        "case_crossing_lambda_median": statistics.median(crossed) if crossed else None,
        "weights": {str(w): {**weights[w], "mean_delta_loss": mean_dv+w*mean_dq}
                    for w in WEIGHTS},
        "lambda_10_by_climate_class": dict(sorted(by_class.items())),
    }


def verify_source_paths(records: list[dict], family: str) -> None:
    """Fail closed if the purported frozen archive has different path identities.

    This checks source identifiers only; without signed frozen file hashes it
    cannot establish that generated water/Q outputs have not been manipulated.
    """
    require(family in SOURCE_PATHS, f"Unknown family {family!r}")
    observed = {row["key"][:3] for row in records}
    require(observed == SOURCE_PATHS[family],
            f"{family}: source climate-path/seed catalog mismatch")


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
        value = report[output]
        require(value is not None and math.isfinite(value)
                and abs(value-expected) <= 0.0000005,
                f"{report['family']}: manuscript checkpoint mismatch: {output}")
    # Fail closed for EVERY displayed manuscript decision weight, not only λ=10.
    for weight, expected in EXPECTED_WEIGHT_GRID[report["family"]].items():
        row = report["weights"][str(weight)]
        require((row["v3"], row["v2"], row["tied"]) == expected[:3],
                f"{report['family']}: lambda={weight} preference mismatch")
        value = row["mean_delta_loss"]
        require(math.isfinite(value) and abs(value - expected[3]) <= 0.0000005,
                f"{report['family']}: lambda={weight} mean difference mismatch")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_frozen_sha256(path: Path, expected_sha256: str, label: str) -> str:
    """Verify the exact bytes of a privately frozen CSV, before interpretation.

    The expected hash must originate from a separately preserved, trusted
    author manifest. A hash computed from the same unchecked file is not
    independent provenance evidence.
    """
    require(len(expected_sha256) == 64
            and all(ch in "0123456789abcdefABCDEF" for ch in expected_sha256),
            f"{label}: expected SHA-256 must be 64 hexadecimal characters")
    actual = file_sha256(path)
    require(actual == expected_sha256.lower(),
            f"{label}: frozen source SHA-256 mismatch")
    return actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-c", type=Path, required=True)
    parser.add_argument("--regime-r1", type=Path, required=True)
    parser.add_argument("--expected-c-sha256",
                        help="Trusted independent SHA-256 of the frozen C CSV")
    parser.add_argument("--expected-r1-sha256",
                        help="Trusted independent SHA-256 of the frozen R1 CSV")
    parser.add_argument("--verify-paper", action="store_true",
                        help="Reject output inconsistent with six-decimal manuscript checkpoints")
    args = parser.parse_args()
    try:
        require(bool(args.expected_c_sha256) == bool(args.expected_r1_sha256),
                "Both trusted frozen CSV SHA-256 values are required together")
        if args.expected_c_sha256:
            verify_frozen_sha256(args.cohort_c, args.expected_c_sha256, "C")
            verify_frozen_sha256(args.regime_r1, args.expected_r1_sha256, "R1")
        reports = []
        for family, path in (("C", args.cohort_c), ("R1", args.regime_r1)):
            records = load_records(path)
            data = analyze_family(records, family)
            if args.verify_paper:
                verify_source_paths(records, family)
                verify_paper(data)
            data["source_csv_sha256"] = file_sha256(path)
            reports.append(data)
    except (AuditError, OSError) as error:
        print(f"AUDIT FAILED: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "audit": "synthetic matched-scenario output post-processing",
        "manuscript_numeric_checkpoint": "PASS" if args.verify_paper else "NOT_REQUESTED",
        "frozen_source_sha256_check": "PASS" if args.expected_c_sha256 else "NOT_REQUESTED",
        "limits": "No simulation-generator replay, field validation, yield effect, or real water saving is established.",
        "families": reports,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

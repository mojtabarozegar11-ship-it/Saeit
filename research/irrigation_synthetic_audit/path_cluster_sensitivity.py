#!/usr/bin/env python3
"""R01 climate-path sensitivity diagnostics for SYNTHETIC paired outcomes.

Works only on an existing paired_scenario_audit.py JSON report; does not replay
weather, observe farms, validate forecasts, estimate yield or claim profit.
No independence assumption or inferential confidence interval is imposed.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

CLASSES = ("dry", "medium", "wet")
OUTCOMES = ("mean_delta_water_m3", "mean_delta_q100")
MAX_BYTES = 8 * 1024 * 1024


class SensitivityError(ValueError):
    """Incomplete or inconsistent synthetic audit report."""


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise SensitivityError(message)


def finite(value: object, label: str) -> float:
    ensure(type(value) in (int, float) and math.isfinite(value),
           f"{label}: expected finite numeric value")
    return float(value)


def positive_int(value: object, expected: int, label: str) -> None:
    ensure(type(value) is int and value == expected,
           f"{label}: expected {expected}")


def summarize_family(report: dict) -> dict:
    """Validate 12 entire path blocks and derive deterministic LOO influence.

    This *describes* variability between 12 simulated climate paths; it cannot
    establish that paths are independent random samples or that a t/bootstrapped
    interval has population coverage.
    """
    ensure(isinstance(report, dict), "family report must be an object")
    family = report.get("family")
    ensure(family in ("C", "R1"), "unknown family")
    positive_int(report.get("matched_keys"), 540, "matched keys")
    positive_int(report.get("climate_paths"), 12, "climate paths")
    positive_int(report.get("record_count"), 1620 if family == "C" else 2160,
                 "policy rows")
    paths = report.get("climate_path_effects")
    ensure(isinstance(paths, list) and len(paths) == 12, "exactly 12 paths required")
    seen = set()
    counts = Counter()
    path_values = {}
    for p in paths:
        ensure(isinstance(p, dict), "path must be an object")
        cohort, seed, climate = p.get("cohort"), p.get("seed"), p.get("climate_class")
        ensure(isinstance(cohort, str) and cohort.startswith("C-" if family == "C" else "R-"),
               "family/path prefix conflict")
        ensure(type(seed) is int and seed >= 0, "seed must be a nonnegative integer")
        ensure(climate in CLASSES and cohort.startswith(
            ("C-" if family == "C" else "R-") + climate + "-"),
            "path climate class mismatch")
        key = (cohort, seed, climate)
        ensure(key not in seen, "duplicate climate path")
        seen.add(key)
        counts[climate] += 1
        positive_int(p.get("matched_keys"), 45, "path matched keys")
        path_values[key] = {field: finite(p.get(field), field) for field in OUTCOMES}
    ensure(all(counts[c] == 4 for c in CLASSES), "expected 4 paths per climate class")

    leaves = report.get("leave_one_climate_path_out")
    ensure(isinstance(leaves, list) and len(leaves) == 12, "12 LOO rows required")
    leaves_by_key = {}
    for item in leaves:
        ensure(isinstance(item, dict), "LOO row must be an object")
        key = (item.get("excluded_path"), item.get("excluded_seed"),
               item.get("climate_class"))
        ensure(key in path_values and key not in leaves_by_key,
               "unknown or duplicate excluded path")
        positive_int(item.get("remaining_matched_keys"), 495, "LOO matched keys")
        leaves_by_key[key] = item
    classes = report.get("climate_class_effects")
    ensure(isinstance(classes, dict) and set(classes) == set(CLASSES),
           "climate class summaries incomplete")

    outputs = {}
    for field in OUTCOMES:
        values = [path_values[key][field] for key in sorted(path_values)]
        grand = statistics.fmean(values)
        declared = finite(report.get(field), "declared " + field)
        ensure(math.isclose(grand, declared, rel_tol=1e-10, abs_tol=1e-7),
               "global mean disagrees with 12 path means for " + field)
        class_means = {}
        for climate in CLASSES:
            item = classes[climate]
            ensure(isinstance(item, dict), "class summary must be an object")
            positive_int(item.get("matched_keys"), 180, "class matched keys")
            positive_int(item.get("climate_paths"), 4, "class paths")
            subset = [vals[field] for key, vals in path_values.items()
                      if key[2] == climate]
            mean = statistics.fmean(subset)
            ensure(math.isclose(mean, finite(item.get(field), "declared class mean"),
                                rel_tol=1e-10, abs_tol=1e-7),
                   "class mean inconsistent for " + field)
            class_means[climate] = mean
        deletion = []
        for key in sorted(path_values):
            # Independent path-based arithmetic, never 540 pseudo-independent rows.
            loo = statistics.fmean(path_values[k][field] for k in path_values if k != key)
            claimed = finite(leaves_by_key[key].get(field), "declared LOO")
            ensure(math.isclose(loo, claimed, rel_tol=1e-10, abs_tol=1e-7),
                   "LOO disagreement for " + field)
            influence = grand - loo
            reversal = (grand > 0 and loo < 0) or (grand < 0 and loo > 0)
            deletion.append({
                "excluded_path": key[0], "excluded_seed": key[1],
                "climate_class": key[2], "remaining_paths": 11,
                "remaining_matched_keys": 495, "leave_one_path_mean": loo,
                "influence_overall_minus_leave_one_out": influence,
                "opposite_sign": reversal,
            })
        outputs[field] = {
            "unit": "m3" if field.endswith("_m3") else "simulated plot-days",
            "finite_archive_mean": grand, "path_sd_descriptive": statistics.stdev(values),
            "path_se_descriptive_only": statistics.stdev(values) / math.sqrt(12),
            "path_range": [min(values), max(values)],
            "class_means": class_means,
            "max_abs_leave_one_path_influence": max(
                abs(row["influence_overall_minus_leave_one_out"]) for row in deletion),
            "sign_reversal_on_deletion": any(row["opposite_sign"] for row in deletion),
            "leave_one_path_out": deletion,
        }
    return {
        "family": family, "source": "synthetic-model-output-only",
        "climate_path_blocks": 12,
        "factorial_settings_per_path": 45,
        "interval_coverage_claim": False,
        "field_validity_claim": False,
        "uncertainty_note": "Descriptive path spread only; paths not demonstrated independent draws.",
        "outcomes": outputs,
    }


def _unique_pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        ensure(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def load_report(path: Path) -> dict:
    ensure(path.is_file() and not path.is_symlink(), "input must be a regular non-symlink file")
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    ensure(len(raw) <= MAX_BYTES, "input too large")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                         parse_constant=lambda x: (_ for _ in ()).throw(
                             SensitivityError("nonfinite JSON constant: " + x)))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SensitivityError("invalid JSON report") from exc
    ensure(isinstance(obj, dict) and isinstance(obj.get("families"), list),
           "expected synthetic paired report with families array")
    ensure(len(obj["families"]) == 2, "exactly C and R1 reports required")
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-json", type=Path, required=True,
                        help="Existing paired_scenario_audit.py JSON; synthetic outputs only")
    args = parser.parse_args()
    try:
        report = load_report(args.audit_json)
        families = [summarize_family(x) for x in report["families"]]
        ensure({x["family"] for x in families} == {"C", "R1"},
               "families must be C and R1, not duplicates")
    except (SensitivityError, OSError, TypeError) as exc:
        print("SENSITIVITY FAILED: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({
        "scope": "synthetic output sensitivity; NOT field inference",
        "source_verified_independently": False,
        "generator_replayed": False,
        "decision_time_validated": False,
        "families": families,
    }, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

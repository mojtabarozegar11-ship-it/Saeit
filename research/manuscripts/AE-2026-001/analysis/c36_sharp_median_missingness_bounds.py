#!/usr/bin/env python3
"""Reproduce AE-2026-001 C36 sharp finite-frame median bounds from committed 2026-only WDI CSV.

This is a deterministic descriptive sensitivity analysis, not a world-weighted estimate,
an imputation procedure, a new estimator, a confidence interval or a journal-ready result.
"""
import csv
import hashlib
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv"
EXPECTED_SHA256 = "715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169"

def calculate():
    source_bytes = SOURCE.read_bytes()
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha != EXPECTED_SHA256:
        raise ValueError(f"Source bytes changed; expected {EXPECTED_SHA256}, got {actual_sha}")
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    observed = []
    for record in records:
        a = record["ag_value_added_per_worker_2000_constant2015usd"]
        b = record["ag_value_added_per_worker_2019_constant2015usd"]
        if not a or not b:
            continue
        x, y = float(a), float(b)
        if math.isfinite(x) and math.isfinite(y) and x > 0 and y > 0:
            observed.append((100 * math.log(y / x) / 19, record["country_iso3"]))
    observed.sort()
    N, n = len(records), len(observed)
    missing = N - n
    assert (N, n, missing) == (217, 157, 60)
    rank = (N + 1) // 2
    lower = observed[rank - missing - 1]
    upper = observed[rank - 1]
    observed_median = observed[(n - 1) // 2]
    positive = sum(value > 0 for value, _ in observed)
    assert positive == 132
    assert lower[1] == "LBR" and upper[1] == "SWE" and observed_median[1] == "BGR"
    assert lower[0] > 0
    return {
        "input_sha256": actual_sha,
        "frame_economies": N,
        "observed_pairs": n,
        "unobserved_pairs": missing,
        "observed_positive": positive,
        "observed_nonpositive": n - positive,
        "full_frame_median_rank_1_based": rank,
        "lower_observed_rank_1_based": rank - missing,
        "upper_observed_rank_1_based": rank,
        "lower_bound_log_pp_per_year": lower[0],
        "lower_boundary_iso3": lower[1],
        "observed_median_log_pp_per_year": observed_median[0],
        "upper_bound_log_pp_per_year": upper[0],
        "upper_boundary_iso3": upper[1],
        "positive_sign_identified_for_finite_frame": True,
        "scope": "2026-only, 217-record equal-economy frame, 2000-2019; not 155-country vintage cohort"
    }

if __name__ == "__main__":
    print(json.dumps(calculate(), indent=2, sort_keys=True))

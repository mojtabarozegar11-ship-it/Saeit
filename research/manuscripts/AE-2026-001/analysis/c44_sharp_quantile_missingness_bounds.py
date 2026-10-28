#!/usr/bin/env python3
"""AE-C44: sharp finite-frame nearest-rank quantile bounds; source-locked 2026 WDI only.

No imputation, inferential CI, 2024/2025 vintage replication, or population estimate.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

EXPECTED_SHA256 = "715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169"
EXPECTED_ROWS = 217
EXPECTED_OBSERVED = 157
EXPECTED_MISSING = 60
PERCENTILES = (0.10, 0.25, 0.50, 0.75, 0.90)

def run(path):
    path = Path(path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("WDI source SHA256 mismatch: refuse analysis")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = ("country_iso3",
                    "ag_value_added_per_worker_2000_constant2015usd",
                    "ag_value_added_per_worker_2019_constant2015usd")
        if not set(required).issubset(reader.fieldnames or ()):
            raise ValueError("Source schema mismatch")
        rows = list(reader)
    if len(rows) != EXPECTED_ROWS or len({r["country_iso3"] for r in rows}) != EXPECTED_ROWS:
        raise ValueError("Unexpected country frame or duplicate keys")
    observed = []
    for r in rows:
        try:
            y0 = float(r[required[1]])
            y1 = float(r[required[2]])
        except (ValueError, TypeError):
            continue
        if not (math.isfinite(y0) and math.isfinite(y1) and y0 > 0 and y1 > 0):
            continue
        observed.append((100.0 * math.log(y1 / y0) / 19.0, r["country_iso3"]))
    observed.sort()
    n, nobs = len(rows), len(observed)
    m = n - nobs
    if (nobs, m) != (EXPECTED_OBSERVED, EXPECTED_MISSING):
        raise ValueError("Expected 157 observed and 60 unobserved rates")
    result = {"source_sha256": digest, "frame_n": n, "observed_n": nobs,
              "unobserved_n": m, "indicator": "NV.AGR.EMPL.KD",
              "growth_unit": "annual log percentage points, 2000-2019",
              "quantile_rule": "nearest rank: k=ceil(p*N), 1-indexed",
              "bounds": []}
    for p in PERCENTILES:
        k = math.ceil(p * n)
        # Missing values may be arbitrarily low or high; bounds are infimum/supremum.
        lo = observed[k - m - 1] if k > m else None
        hi = observed[k - 1] if k <= nobs else None
        result["bounds"].append({
            "p": p, "full_frame_rank": k,
            "lower_infimum": None if lo is None else lo[0],
            "lower_witness_iso3": None if lo is None else lo[1],
            "lower_unbounded": lo is None,
            "upper_supremum": None if hi is None else hi[0],
            "upper_witness_iso3": None if hi is None else hi[1],
            "upper_unbounded": hi is None})
    med = result["bounds"][2]
    if abs(med["lower_infimum"] - 1.4239594820464043) > 1e-9 or abs(med["upper_supremum"] - 3.6898758409488392) > 1e-9:
        raise ValueError("C36 median cross-check failed")
    return result

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python c44_sharp_quantile_missingness_bounds.py source_locked_wdi.csv")
    print(json.dumps(run(sys.argv[1]), indent=2, ensure_ascii=False))

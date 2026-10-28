#!/usr/bin/env python3
"""C48: exact adversarial deletion threshold for the 2019-2023 WDI mean contrast.
Usage: python c48_minimum_deletion_sign_flip.py LOCKED_WDI_CSV
Never fetches data or treats post hoc exclusions as justified cleaning.
"""
import csv
import hashlib
import math
import sys
from pathlib import Path
from statistics import mean

SHA256 = "715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169"
K0 = "ag_value_added_per_worker_2000_constant2015usd"
K19 = "ag_value_added_per_worker_2019_constant2015usd"
K23 = "ag_value_added_per_worker_2023_constant2015usd"

def positive(x):
    try:
        z = float(x)
        return math.isfinite(z) and z > 0
    except (ValueError, TypeError):
        return False

def main(path):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise SystemExit("Source SHA256 mismatch; NO RESULT")
    with Path(path).open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != 217 or len({r["country_iso3"] for r in rows}) != 217:
        raise SystemExit("Invalid 217-economy source frame")
    valid = []
    for r in rows:
        if positive(r[K19]) and positive(r[K23]):
            valid.append((r["country_iso3"],
                          100 * math.log(float(r[K23]) / float(r[K19])) / 4,
                          positive(r[K0])))
    baseline = [g for _, g, present in valid if present]
    missing = [(iso, g) for iso, g, present in valid if not present]
    if (len(valid), len(baseline), len(missing)) != (169, 153, 16):
        raise SystemExit("Cohort mismatch; NO RESULT")
    reference_mean = mean(baseline)
    ordered = sorted(missing, key=lambda x: (-x[1], x[0]))
    print("k,remaining_n,deleted_iso3,mean_difference_log_pp_per_year")
    first_flip = None
    for k in range(17):
        excluded = {iso for iso, _ in ordered[:k]}
        remain = [g for iso, g, _ in valid if iso not in excluded]
        delta = mean(remain) - reference_mean
        print(f"{k},{len(remain)},\"{' '.join(iso for iso, _ in ordered[:k])}\",{delta:.12f}")
        if delta < 0 and first_flip is None:
            first_flip = k
    if first_flip != 3:
        raise SystemExit(f"Unexpected sign-flip threshold: {first_flip}")
    print("NOTE: adversarial post hoc sensitivity only; not an exclusion recommendation.", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])

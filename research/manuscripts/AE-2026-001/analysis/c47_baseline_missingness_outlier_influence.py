#!/usr/bin/env python3
"""C47: descriptive influence and robust location of 2019-2023 WDI growth.
No external downloads, imputations, causal inference, or historical-vintage claims.
Usage: python c47_baseline_missingness_outlier_influence.py PATH_TO_LOCKED_CSV
"""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from statistics import mean, median

EXPECTED_SHA256 = "715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169"
KEY0 = "ag_value_added_per_worker_2000_constant2015usd"
KEY19 = "ag_value_added_per_worker_2019_constant2015usd"
KEY23 = "ag_value_added_per_worker_2023_constant2015usd"

def positive(raw):
    try:
        x = float(raw)
        return math.isfinite(x) and x > 0
    except (ValueError, TypeError):
        return False

def trimmed_mean(values, fraction):
    a = sorted(values)
    k = math.floor(len(a) * fraction)
    return mean(a[k:len(a)-k])

def main(path):
    data = Path(path).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != EXPECTED_SHA256:
        raise SystemExit(f"Source SHA256 mismatch: {actual}; NO RESULT")
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != 217 or len({r["country_iso3"] for r in rows}) != 217:
        raise SystemExit("Unexpected country frame; NO RESULT")
    a = []
    for r in rows:
        if positive(r[KEY19]) and positive(r[KEY23]):
            a.append(dict(iso=r["country_iso3"], name=r["country_name"],
                          region=r["region"].strip(),
                          growth=100*math.log(float(r[KEY23])/float(r[KEY19]))/4,
                          baseline=positive(r[KEY0])))
    b = [x for x in a if x["baseline"]]
    m = [x for x in a if not x["baseline"]]
    if (len(a),len(b),len(m)) != (169,153,16):
        raise SystemExit("Cohort count mismatch; NO RESULT")
    g_all = [x["growth"] for x in a]
    g_b = [x["growth"] for x in b]
    mu_b = mean(g_b)
    shift = mean(g_all) - mu_b
    influence = []
    for x in m:
        # Fixed-169 denominator accounting contribution, not leave-one-out effect.
        contrib = (x["growth"]-mu_b)/len(a)
        # Actual deletion recalculates the mean with denominator 168.
        loo_shift = mean([y["growth"] for y in a if y["iso"] != x["iso"]]) - mu_b
        influence.append(dict(iso=x["iso"], name=x["name"], region=x["region"],
                              growth=x["growth"], fixed_frame_contribution=contrib,
                              leave_one_out_shift=loo_shift))
    influence.sort(key=lambda x: abs(x["fixed_frame_contribution"]), reverse=True)
    assert math.isclose(sum(x["fixed_frame_contribution"] for x in influence), shift, abs_tol=1e-11)
    output = dict(source_sha256=actual, n_frame=len(rows), n_2019_2023=len(a),
                  n_baseline=len(b), n_missing_baseline=len(m),
                  mean_shift=shift,
                  median_shift=median(g_all)-median(g_b),
                  trimmed_10pct_shift=trimmed_mean(g_all,.1)-trimmed_mean(g_b,.1),
                  trimmed_20pct_shift=trimmed_mean(g_all,.2)-trimmed_mean(g_b,.2),
                  influential_added_economies=influence,
                  caveat="Descriptive WDI snapshot only; not causal, not vintage matched, not ILOSTAT validation.")
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])

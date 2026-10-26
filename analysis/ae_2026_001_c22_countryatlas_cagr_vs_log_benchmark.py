#!/usr/bin/env python3
"""AE C22: compare documented countryatlas CAGR convention with WDI log growth.

This is a source-locked *formula-equivalent* numerical comparator, NOT an
execution of the countryatlas R package or its compare_vintages() function.
No new WDI vintage, statistical novelty, or causal inference is claimed.
"""
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

SOURCE = Path("research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv")
EXPECTED_SHA256 = "715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169"
FIELDS = {
    2000: "ag_value_added_per_worker_2000_constant2015usd",
    2019: "ag_value_added_per_worker_2019_constant2015usd",
    2023: "ag_value_added_per_worker_2023_constant2015usd",
}

def positive(v):
    try:
        z = float(v)
        return math.isfinite(z) and z > 0
    except (TypeError, ValueError):
        return False

def compute(rows, first, last, expected_n):
    years = last - first
    out = []
    for row in rows:
        p0, p1 = row[FIELDS[first]], row[FIELDS[last]]
        if not (positive(p0) and positive(p1)):
            continue
        annual_log = math.log(float(p1) / float(p0)) / years
        log_pp = 100 * annual_log
        # countryatlas growth_rate(type="cagr") documented compound rate,
        # evaluated here on a two-endpoint panel with first observed year fixed.
        cagr_pp = 100 * math.expm1(annual_log)
        out.append({
            "iso3c": row["country_iso3"],
            "log_pp_per_year": log_pp,
            "cagr_percent_per_year": cagr_pp,
            "cagr_minus_log_pp": cagr_pp - log_pp,
        })
    if len(out) != expected_n:
        raise SystemExit(f"FAIL CLOSED: {first}-{last} cohort {len(out)} != {expected_n}")
    logs = sorted(x["log_pp_per_year"] for x in out)
    cagr = sorted(x["cagr_percent_per_year"] for x in out)
    # Strict monotonicity of expm1 guarantees rank equivalence for finite inputs.
    if not all(math.isclose(c, 100*math.expm1(g/100), abs_tol=1e-10) for g,c in zip(logs,cagr)):
        raise SystemExit("FAIL CLOSED: monotone rank transform identity")
    if sum(math.copysign(1,x["log_pp_per_year"]) != math.copysign(1,x["cagr_percent_per_year"]) for x in out):
        raise SystemExit("FAIL CLOSED: unexpected sign disagreement")
    differences = [x["cagr_minus_log_pp"] for x in out]
    most = max(out, key=lambda x: abs(x["cagr_minus_log_pp"]))
    return {
        "period": f"{first}-{last}", "n": len(out),
        "median_log_pp": statistics.median(logs),
        "median_cagr_percent": statistics.median(cagr),
        "mean_cagr_minus_log_pp": statistics.mean(differences),
        "median_cagr_minus_log_pp": statistics.median(differences),
        "count_abs_difference_over_0_1_pp": sum(abs(d) > 0.1 for d in differences),
        "count_abs_difference_over_0_5_pp": sum(abs(d) > 0.5 for d in differences),
        "sign_agreement_count": len(out),
        "rank_order_identical": True,
        "max_abs_difference_case": most,
        "rows": sorted(out, key=lambda x: x["iso3c"]),
    }

def main():
    actual_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if actual_hash != EXPECTED_SHA256:
        raise SystemExit(f"FAIL CLOSED: WDI source SHA256 {actual_hash} != expected")
    with SOURCE.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != 217 or len({r["country_iso3"] for r in rows}) != 217:
        raise SystemExit("FAIL CLOSED: expected 217 distinct nonaggregate economies")
    a = compute(rows, 2000, 2019, 157)
    b = compute(rows, 2019, 2023, 169)
    if not math.isclose(a["median_log_pp"], 2.3555752946417114, abs_tol=1e-9):
        raise SystemExit("FAIL CLOSED: 2000-2019 median differs")
    if not math.isclose(b["median_log_pp"], 0.9751104652311193, abs_tol=1e-9):
        raise SystemExit("FAIL CLOSED: 2019-2023 median differs")
    report = {
        "source_sha256": actual_hash,
        "method": "Formula-equivalent documented countryatlas growth_rate(type='cagr') vs annualized natural-log growth; countryatlas package NOT executed.",
        "reference": "https://www.rdocumentation.org/packages/countryatlas/versions/3.0.0/topics/growth_rate",
        "limitations": "No historical-vintage compare_vintages execution, no independent data, no novel estimator, no causal result.",
        "periods": [a,b],
    }
    target = Path("research_outputs/AE-2026-001/c22_countryatlas_cagr_vs_log_benchmark.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    for z in (a,b):
        print(z["period"], "n", z["n"], "median log", round(z["median_log_pp"], 6),
              "median CAGR", round(z["median_cagr_percent"], 6),
              "max diff", z["max_abs_difference_case"]["iso3c"],
              round(z["max_abs_difference_case"]["cagr_minus_log_pp"], 6))
    print("PASS: source-locked formula comparator, no claim of running countryatlas.")

if __name__ == "__main__":
    main()

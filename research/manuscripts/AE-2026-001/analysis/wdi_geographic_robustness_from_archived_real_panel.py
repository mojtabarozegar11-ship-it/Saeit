#!/usr/bin/env python3
"""Auditable robustness of WDI agricultural labor-productivity descriptions.

Source: official, archived, 2026-10-25 WDI NV.AGR.EMPL.KD country CSV.
This is descriptive analysis, not causal inference, a convergence test or a
novelty claim. Requires no paid packages, internet or external credentials.
"""
import csv
import json
import math
import statistics
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INPUT = BASE / "AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv"
COL = ("ag_value_added_per_worker_2000_constant2015usd",
       "ag_value_added_per_worker_2019_constant2015usd",
       "ag_value_added_per_worker_2023_constant2015usd")
OUT = BASE / "AE-2026-001_REAL_WDI_REGION_EXCLUSION_SENSITIVITY_2026-10-25.json"

def median(z):
    return statistics.median(z) if z else None

def mean(z):
    return statistics.mean(z) if z else None

def growth(row, idx):
    initial, end = row["v"][0], row["v"][idx]
    if initial is None or end is None:
        return None
    return math.log(end / initial) / (19 if idx == 1 else 23)

def summary(rows, idx):
    vals = [growth(row, idx) for row in rows]
    vals = sorted(v for v in vals if v is not None)
    return {"n":len(vals), "median":median(vals), "mean":mean(vals)}

def execute():
    with INPUT.open(newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        raw = list(rd)
    assert len(raw) == 217, "Unexpected official panel country count"
    rows = []
    for r in raw:
        v = [float(r[c]) if r[c] else None for c in COL]
        assert all(x is None or (math.isfinite(x) and x > 0) for x in v)
        rows.append({"code":r["country_iso3"],"region":r["region"].strip(),"v":v})
    assert len(set(r["code"] for r in rows)) == len(rows)
    all_regions = sorted(set(r["region"] for r in rows))
    balanced = [r for r in rows if growth(r, 1) is not None and growth(r, 2) is not None]
    assert len(balanced) == 153
    output = {
        "source":"WDI NV.AGR.EMPL.KD country observations, fetched and source-archived 2026-10-25",
        "archived_panel":str(INPUT.relative_to(BASE)),
        "source_type":"genuine official observations (not synthetic test values)",
        "nonaggregate_economies":len(rows),
        "complete_three_year_economies":len(balanced),
        "available_pair":{str(y): summary(rows, i) for i,y in [(1,2019),(2,2023)]},
        "balanced_panel":{str(y): summary(balanced, i) for i,y in [(1,2019),(2,2023)]},
        "leave_one_region_out":[],
        "five_percent_tail_trimmed_balanced":{},
        "regional_coverage":[]
    }
    assert output["available_pair"]["2019"]["n"] == 157
    assert output["available_pair"]["2023"]["n"] == 153
    assert abs(output["available_pair"]["2019"]["median"] - 0.023555752946417118) < 1e-12
    assert abs(output["available_pair"]["2023"]["median"] - 0.02224483704398673) < 1e-12
    for region in all_regions:
        included = [r for r in balanced if r["region"] != region]
        a = summary(included, 1)
        b = summary(included, 2)
        output["leave_one_region_out"].append({
            "excluded_region":region,
            "excluded_count":len(balanced)-len(included),
            "retained_count":len(included),
            "median_annual_log_growth_2000_2019":a["median"],
            "median_annual_log_growth_2000_2023":b["median"],
            "difference_later_minus_earlier":b["median"]-a["median"]
        })
        group = [r for r in rows if r["region"] == region]
        output["regional_coverage"].append({
            "region":region, "all_economies":len(group),
            "observed_2000":sum(r["v"][0] is not None for r in group),
            "observed_2019":sum(r["v"][1] is not None for r in group),
            "observed_2023":sum(r["v"][2] is not None for r in group),
            "complete_three_year_economies":sum(r in balanced for r in group)
        })
    for idx, year in [(1,2019),(2,2023)]:
        z = sorted(growth(r,idx) for r in balanced)
        k = math.floor(len(z)*0.05)
        trimmed = z[k:len(z)-k]
        output["five_percent_tail_trimmed_balanced"][str(year)] = {
            "removed_each_tail":k,"retained":len(trimmed),
            "trimmed_mean":mean(trimmed),"trimmed_median":median(trimmed)}
    output["limitations"] = [
        "Descriptive economy-weighted rates, NOT agricultural-worker-weighted global rates.",
        "The 2000-to-2019 and 2000-to-2023 horizons overlap: the annualized difference is NOT a pure 2019-to-2023 economic shock.",
        "Missing source observations are not random and zeros are not imputed.",
        "One-region-exclusion tests reveal composition sensitivity, not statistical significance.",
        "ILO-modeled employment and national-account breaks can alter apparent productivity.",
        "No new theory, causality, convergence or guaranteed publication novelty follows."
    ]
    OUT.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(output,indent=2,ensure_ascii=False))
if __name__ == "__main__":
    execute()

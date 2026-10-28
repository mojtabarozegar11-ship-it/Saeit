#!/usr/bin/env python3
"""AE-C45: exact 2019–2023 growth comparison by 2000-baseline availability.

Descriptive within the 2026 source snapshot only. Not causal, not MAR testing,
not a cross-vintage comparison, and not a world-population-weighted estimate.
"""
import csv
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv"
FIELDS = {y: f"ag_value_added_per_worker_{y}_constant2015usd" for y in (2000, 2019, 2023)}

def positive(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else None
    except (TypeError, ValueError):
        return None

def summarize(rows):
    rates = [r["growth_log_pp_per_year"] for r in rows]
    levels = [r["level_2019"] for r in rows]
    return {
        "n": len(rows),
        "median_growth_log_pp_per_year": statistics.median(rates),
        "mean_growth_log_pp_per_year": statistics.mean(rates),
        "positive_growth_n": sum(x > 0 for x in rates),
        "negative_growth_n": sum(x < 0 for x in rates),
        "median_2019_level_constant_2015_usd": statistics.median(levels),
    }

def compute():
    with SOURCE.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 217 or len({r["country_iso3"] for r in rows}) != 217:
        raise ValueError("Source frame is not the expected 217 distinct economy codes")
    full, baseline, late = [], [], []
    by_region = {}
    for r in rows:
        a, b, c = (positive(r[FIELDS[y]]) for y in (2000, 2019, 2023))
        if b is None or c is None:
            continue
        x = {"iso3": r["country_iso3"], "region": r["region"].strip(),
             "level_2019": b, "growth_log_pp_per_year": 100 * math.log(c/b) / 4}
        full.append(x)
        (baseline if a is not None else late).append(x)
        reg = by_region.setdefault(x["region"], {"with_2000": [], "without_2000": []})
        reg["with_2000" if a is not None else "without_2000"].append(x)
    if (len(full), len(baseline), len(late)) != (169, 153, 16):
        raise ValueError("Unexpected availability masks; do not report stale numbers")
    return {
        "analysis": "C45 baseline-availability selection diagnostic",
        "indicator": "NV.AGR.EMPL.KD",
        "source_csv": SOURCE.name,
        "source_git_blob_sha": "d4910ff78219f9e5097c6301a6fbfa7752bbf4f9",
        "full_2019_2023": summarize(full),
        "has_2000_baseline": summarize(baseline),
        "no_2000_baseline": summarize(late),
        "full_minus_baseline_median_log_pp_per_year":
            statistics.median(x["growth_log_pp_per_year"] for x in full)
            - statistics.median(x["growth_log_pp_per_year"] for x in baseline),
        "late_entry_iso3": sorted(x["iso3"] for x in late),
        "region_counts": {region: {
            "with_2000": len(groups["with_2000"]),
            "without_2000": len(groups["without_2000"])
        } for region, groups in sorted(by_region.items())},
        "limitations": [
            "Selection is based on 2000 availability, not randomized assignment.",
            "The 169 and 153 frames have different membership and are not interchangeable.",
            "No evidence for missing at random, causal explanations, or a global weighted estimand.",
            "No historical-vintage benchmark or independent employment-source validation."
        ],
        "scientific_gate": "MAJOR_REVISION_NO_SUBMISSION"
    }

if __name__ == "__main__":
    print(json.dumps(compute(), indent=2, ensure_ascii=False))

#!/usr/bin/env python3
"""Non-overlapping annual log-growth comparisons using archived ACTUAL WDI observations.

Independent of the earlier 2000-based overlapping-window sensitivity script.
The source file is a previously downloaded genuine official World Bank panel.
No imputation, simulated data, causality, or worker-weighted world estimate.
Python 3.11 standard library only; read-only source; compact JSON output.
"""
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INPUT = BASE / "AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv"
OUTPUT = BASE / "AE-2026-001_NONOVERLAPPING_2000_2019_VS_2019_2023_REAL_WDI_2026-10-25.json"
FIELDS = [
    "ag_value_added_per_worker_2000_constant2015usd",
    "ag_value_added_per_worker_2019_constant2015usd",
    "ag_value_added_per_worker_2023_constant2015usd",
]

def median(x):
    return statistics.median(x) if x else None

def summarize(rows, field):
    values = [r[field] for r in rows]
    return {
        "n": len(values),
        "mean_annual_log_growth": statistics.mean(values),
        "median_annual_log_growth": median(values),
        "positive": sum(v > 0 for v in values),
        "negative": sum(v < 0 for v in values),
        "zero": sum(v == 0 for v in values),
    }

def main():
    with INPUT.open(newline="", encoding="utf-8") as handle:
        source = list(csv.DictReader(handle))
    assert len(source) == 217, "WDI source panel unexpectedly changed"
    assert len({r["country_iso3"] for r in source}) == len(source)
    records = []
    for r in source:
        if any(not r[field] for field in FIELDS):
            continue
        y0, y19, y23 = [float(r[field]) for field in FIELDS]
        if not all(math.isfinite(v) and v > 0 for v in (y0, y19, y23)):
            continue
        early = math.log(y19 / y0) / 19
        late = math.log(y23 / y19) / 4
        total = math.log(y23 / y0) / 23
        assert abs(19*early + 4*late - 23*total) < 1e-10
        records.append({
            "iso": r["country_iso3"],
            "region": r["region"].strip(),
            "early": early,
            "late": late,
            "total": total,
            "late_minus_early": late - early,
        })
    assert len(records) == 153, "Balanced three-year sample unexpectedly changed"
    result = {
        "source_indicator": "NV.AGR.EMPL.KD",
        "input": INPUT.name,
        "source_type": "actual archived World Bank WDI country observations",
        "economies_in_source": len(source),
        "same_economies_in_all_intervals": len(records),
        "intervals": {
            "2000_2019": summarize(records, "early"),
            "2019_2023": summarize(records, "late"),
            "2000_2023": summarize(records, "total"),
        },
        "within_economy_late_minus_early": summarize(records, "late_minus_early"),
        "by_world_bank_region": {},
        "interpretation_limits": [
            "Each annual rate is a natural-log change divided by elapsed years; it is not a percentage change of the index itself.",
            "Early and late periods do not overlap; the 2000-2023 interval overlaps both by construction.",
            "Country-level means and medians are unweighted by worker count and not a global agricultural-sector aggregate.",
            "The 2019-2023 interval is only four years and sensitive to base-year and revision effects.",
            "Changes in modeled employment and national accounts can mimic economic changes.",
            "Regional coverage is incomplete, especially North America (one complete economy).",
            "No causal effect, policy attribution, significance test, or novelty claim is inferred.",
        ],
    }
    for region in sorted({r["region"] for r in records}):
        group = [r for r in records if r["region"] == region]
        result["by_world_bank_region"][region] = {
            "2000_2019": summarize(group, "early"),
            "2019_2023": summarize(group, "late"),
            "within_economy_change": summarize(group, "late_minus_early"),
        }
    assert abs(result["intervals"]["2019_2023"]["median_annual_log_growth"] - 0.008904395335439335) < 1e-12
    assert result["within_economy_late_minus_early"]["negative"] == 109
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

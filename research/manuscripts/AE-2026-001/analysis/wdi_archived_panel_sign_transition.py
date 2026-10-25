#!/usr/bin/env python3
"""Reproducible paired sign transitions from the archived *real* WDI endpoint CSV.

Exploratory, economy-weighted descriptive counts only. No causal interpretation,
no p-values, no convergence claim, no missing-data imputation.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median

SOURCE = Path("research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv")
YEARS = (2000, 2019, 2023)
COLS = [f"ag_value_added_per_worker_{y}_constant2015usd" for y in YEARS]
LABELS = ("early_positive_late_positive", "early_positive_late_negative",
          "early_negative_late_positive", "early_negative_late_negative")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, default=Path("wdi_sign_transition_artifact"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with args.source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 217:
        raise RuntimeError(f"Unexpected economy count: {len(rows)}")
    seen = set()
    country_records = []
    region_counts = defaultdict(Counter)
    global_counts = Counter()
    missing_by_year = Counter()
    for row in rows:
        iso = row["country_iso3"]
        if iso in seen:
            raise RuntimeError(f"Duplicate country: {iso}")
        seen.add(iso)
        vals = []
        for year, key in zip(YEARS, COLS):
            try:
                value = float(row[key]) if row[key] else float("nan")
            except ValueError:
                raise RuntimeError(f"Invalid source numeric value: {iso} {year}")
            if not math.isfinite(value) or value <= 0:
                missing_by_year[str(year)] += 1
            vals.append(value)
        if not all(math.isfinite(x) and x > 0 for x in vals):
            continue
        early = math.log(vals[1] / vals[0]) / 19
        late = math.log(vals[2] / vals[1]) / 4
        if early == 0 or late == 0:
            raise RuntimeError("Zero growth case: extend sign taxonomy before interpreting")
        label = ("early_positive_" if early > 0 else "early_negative_") + ("late_positive" if late > 0 else "late_negative")
        region = row["region"].strip()
        global_counts[label] += 1
        region_counts[region][label] += 1
        country_records.append({"country_iso3": iso, "country_name": row["country_name"],
                                "region": region, "early_log_growth": early,
                                "late_log_growth": late, "late_minus_early": late - early,
                                "transition": label})
    if len(country_records) != 153:
        raise RuntimeError(f"Unexpected common complete-case panel: {len(country_records)}")
    if tuple(global_counts[k] for k in LABELS) != (79, 49, 11, 14):
        raise RuntimeError(f"Independent source replay mismatch: {dict(global_counts)}")
    country_records.sort(key=lambda r: r["country_iso3"])
    with (args.out / "country_sign_transitions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(country_records[0]))
        writer.writeheader()
        writer.writerows(country_records)
    result = {
        "source_file": str(args.source),
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "indicator": "WDI NV.AGR.EMPL.KD, agriculture forestry and fishing value added per worker",
        "economies_in_archived_source": len(rows),
        "economies_with_all_three_positive_endpoints": len(country_records),
        "source_missing_or_nonpositive_by_year": dict(missing_by_year),
        "intervals": ["2000-2019", "2019-2023"],
        "transition_matrix": {key: global_counts[key] for key in LABELS},
        "region_transition_matrix": {region: {key: c[key] for key in LABELS} for region,c in sorted(region_counts.items())},
        "median_within_economy_late_minus_early": median(r["late_minus_early"] for r in country_records),
        "scope": "descriptive paired signs only; selected observed economies; no causal inference, uncertainty interval or global worker weighting",
    }
    (args.out / "source_backed_sign_transitions.json").write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

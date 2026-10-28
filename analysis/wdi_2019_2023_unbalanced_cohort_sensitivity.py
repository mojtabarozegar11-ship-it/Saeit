#!/usr/bin/env python3
"""AE-2026-001: source-locked, non-overlapping 2019–2023 cohort sensitivity.

Descriptive only. A 2019–2023 rate is not a historical-vintage revision, causal
effect, representative world estimate, or an independently measured employment series.
No network calls, interpolation, zero substitution, or external dependencies.
"""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, median

COL_2000 = "ag_value_added_per_worker_2000_constant2015usd"
COL_2019 = "ag_value_added_per_worker_2019_constant2015usd"
COL_2023 = "ag_value_added_per_worker_2023_constant2015usd"
REQUIRED = ("country_iso3", "country_name", "region", COL_2000, COL_2019, COL_2023)

def positive_number(text):
    if text is None or not text.strip():
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) and value > 0 else None

def describe(items):
    vals = [item["annual_log_pp"] for item in items]
    return {"n": len(vals), "median_annual_log_pp": median(vals),
            "mean_annual_log_pp": mean(vals),
            "positive": sum(v > 0 for v in vals),
            "negative": sum(v < 0 for v in vals),
            "zero": sum(v == 0 for v in vals)}

def run(source):
    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    balanced, additional = [], []
    masks = Counter()
    seen = set()
    with source.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not set(REQUIRED).issubset(reader.fieldnames or []):
            raise ValueError("Official panel required columns missing")
        for row in reader:
            iso = row["country_iso3"].strip()
            if not iso or iso in seen:
                raise ValueError("Missing or duplicate ISO3 country code: " + iso)
            seen.add(iso)
            a, b, c = (positive_number(row[col]) for col in (COL_2000, COL_2019, COL_2023))
            mask = "".join("1" if x is not None else "0" for x in (a, b, c))
            masks[mask] += 1
            if b is None or c is None:
                continue
            item = {"iso3": iso, "region": row["region"].strip(),
                    "annual_log_pp": 100 * math.log(c / b) / 4}
            if a is None:
                additional.append(item)
            else:
                balanced.append(item)
    if len(seen) != 217 or len(balanced) != 153 or len(additional) != 16:
        raise ValueError("Unexpected panel cohort counts; fail closed")
    all_eligible = balanced + additional
    two_outliers = {"CAF", "DJI"}
    if not two_outliers.issubset({x["iso3"] for x in additional}):
        raise ValueError("Predeclared influential cases not in additional cohort")
    without_two = [x for x in all_eligible if x["iso3"] not in two_outliers]
    return {
        "source_path": str(source), "source_sha256": sha256,
        "indicator": "NV.AGR.EMPL.KD",
        "years": [2000, 2019, 2023],
        "mask_counts": dict(sorted(masks.items())),
        "balanced_2000_2019_2023": describe(balanced),
        "new_2019_2023_without_2000": describe(additional),
        "all_2019_2023": describe(all_eligible),
        "all_excluding_CAF_DJI_posthoc": describe(without_two),
        "additional_country_region_counts": dict(sorted(Counter(x["region"] for x in additional).items())),
        "additional_country_rates": sorted(additional, key=lambda x: x["annual_log_pp"]),
        "median_shift_all_minus_balanced_log_pp": median(x["annual_log_pp"] for x in all_eligible) - median(x["annual_log_pp"] for x in balanced),
        "mean_shift_all_minus_balanced_log_pp": mean(x["annual_log_pp"] for x in all_eligible) - mean(x["annual_log_pp"] for x in balanced),
        "mean_shift_after_excluding_CAF_DJI_log_pp": mean(x["annual_log_pp"] for x in without_two) - mean(x["annual_log_pp"] for x in balanced),
        "limitations": [
            "The 16 additional economies have 2019/2023 but not 2000 positive endpoints; the 169-economy estimate is a different cohort estimand.",
            "CAF/DJI exclusion is post-hoc influence analysis, not an outlier-removal mandate.",
            "Rates are country-equal weighted; they are not global worker-weighted aggregates.",
            "The 2019–2023 four-year interval cannot isolate any policy, pandemic, climate or data-revision cause.",
            "This does not resolve historical WDI/ILOSTAT vintages or novelty over countryatlas."
        ],
        "publication_gate": "MAJOR_REVISION_NO_SUBMISSION"
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "additional_country_rates"}, indent=2))

if __name__ == "__main__":
    main()

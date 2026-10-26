#!/usr/bin/env python3
"""AE-2026-001 C16: exact region-stratified descriptive cohort-mean decomposition.

Source-locked original WDI panel; no imputation, causal claims, significance
testing, independent employment estimates, or historical ILOSTAT reconstruction.
"""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean

SOURCE_SHA256 = "715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169"
COLS = ("country_iso3", "region",
        "ag_value_added_per_worker_2000_constant2015usd",
        "ag_value_added_per_worker_2019_constant2015usd",
        "ag_value_added_per_worker_2023_constant2015usd")

def positive(value):
    try:
        n = float(value)
        return n if math.isfinite(n) and n > 0 else None
    except (ValueError, TypeError):
        return None

def load(path):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != SOURCE_SHA256:
        raise ValueError(f"Input SHA256 changed: {actual}")
    seen, balanced, added = set(), [], []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not set(COLS).issubset(reader.fieldnames or []):
            raise ValueError("Missing official source columns")
        for row in reader:
            iso = row["country_iso3"].strip()
            if len(iso) != 3 or iso in seen:
                raise ValueError(f"Invalid or duplicate country: {iso}")
            seen.add(iso)
            a, v19, v23 = [positive(row[c]) for c in COLS[2:]]
            if v19 is None or v23 is None:
                continue
            record = {"iso3": iso, "region": row["region"].strip(),
                      "growth_log_pp_year": 25 * math.log(v23 / v19)}
            (balanced if a is not None else added).append(record)
    if (len(seen), len(balanced), len(added)) != (217, 153, 16):
        raise ValueError("Source cohort counts changed")
    return balanced, added

def decompose(balanced, eligible):
    regions = sorted({r["region"] for r in balanced + eligible})
    base_mean = mean(r["growth_log_pp_year"] for r in balanced)
    full_mean = mean(r["growth_log_pp_year"] for r in eligible)
    records, composition, within = [], 0.0, 0.0
    for region in regions:
        b = [r["growth_log_pp_year"] for r in balanced if r["region"] == region]
        p = [r["growth_log_pp_year"] for r in eligible if r["region"] == region]
        if not b or not p:
            raise ValueError(f"Missing baseline or pooled region: {region}")
        mb, mp = mean(b), mean(p)
        c = (len(p)/len(eligible) - len(b)/len(balanced)) * mb
        w = len(p)/len(eligible) * (mp - mb)
        composition += c
        within += w
        records.append({"region": region, "baseline_n": len(b), "pooled_n": len(p),
                        "baseline_mean_log_pp": mb, "pooled_mean_log_pp": mp,
                        "composition_log_pp": c, "within_region_log_pp": w})
    delta = full_mean - base_mean
    if not math.isclose(delta, composition + within, abs_tol=1e-11):
        raise ArithmeticError("Decomposition identity violated")
    return {"baseline_mean_log_pp": base_mean, "pooled_mean_log_pp": full_mean,
            "delta_log_pp": delta, "composition_log_pp": composition,
            "within_region_log_pp": within, "regions": records}

def run(path):
    balanced, added = load(path)
    all_eligible = balanced + added
    if not {"CAF", "DJI"}.issubset({r["iso3"] for r in added}):
        raise ValueError("Post-hoc sensitivity countries changed cohort")
    without_two = [r for r in all_eligible if r["iso3"] not in ("CAF", "DJI")]
    return {"indicator": "NV.AGR.EMPL.KD", "input_sha256": SOURCE_SHA256,
            "base_n": len(balanced), "added_n": len(added), "pooled_n": len(all_eligible),
            "additional_by_region": dict(sorted(Counter(r["region"] for r in added).items())),
            "full": decompose(balanced, all_eligible),
            "without_CAF_DJI_posthoc": decompose(balanced, without_two),
            "cautions": [
              "Exact algebraic decomposition of country-equal-weighted sample means; not causal Oaxaca identification.",
              "The baseline 153 and pooled 169 differ in missing 2000 endpoints; this is selection, not within-country change.",
              "CAF/DJI exclusion was chosen after inspecting values, not a prespecified exclusion.",
              "No representative-world or historical-vintage inference; no new estimator or significance claim.",
              "MAJOR REVISION / NO SUBMISSION."
            ]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "cautions"}, indent=2))

if __name__ == "__main__":
    main()

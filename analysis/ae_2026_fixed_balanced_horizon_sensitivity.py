#!/usr/bin/env python3
"""AE-2026-001: source-locked 2026 WDI *horizon* sensitivity, NOT vintage revisions.

Computes a fixed 153-economy balanced panel (2000, 2019, 2023) and the
paired 2000–2019 versus 2000–2023 annual log-growth differences.
No imputation, causal interpretation, confidence interval, or ILO count claim.
"""
import argparse
import csv
import hashlib
import json
import math
import pathlib
import statistics

FIELDS = {
    year: f"ag_value_added_per_worker_{year}_constant2015usd"
    for year in (2000, 2019, 2023)
}

def run(panel: pathlib.Path, out: pathlib.Path):
    raw = panel.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    with panel.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"country_iso3", "country_name", "region", *FIELDS.values()}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("WDI panel schema mismatch")
        all_rows = list(reader)
    seen = set()
    balanced = []
    for row in all_rows:
        iso = row["country_iso3"].strip()
        if not iso or iso in seen:
            raise ValueError("Empty/duplicate economy code")
        seen.add(iso)
        try:
            v = [float(row[FIELDS[y]]) for y in (2000, 2019, 2023)]
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(x) and x > 0 for x in v):
            continue
        g19 = math.log(v[1] / v[0]) / 19
        g23 = math.log(v[2] / v[0]) / 23
        balanced.append({
            "iso3": iso,
            "region": row["region"].strip(),
            "g_2000_2019": g19,
            "g_2000_2023": g23,
            "paired_horizon_difference": g23 - g19,
            "sign_changes_between_horizons": (g19 > 0) != (g23 > 0),
        })
    if len(balanced) < 3:
        raise ValueError("Insufficient balanced-country observations")
    a = [row["g_2000_2019"] for row in balanced]
    c = [row["g_2000_2023"] for row in balanced]
    d = [row["paired_horizon_difference"] for row in balanced]
    leave_one_out = [statistics.median(d[:i] + d[i+1:]) for i in range(len(d))]
    report = {
        "source_panel": str(panel),
        "source_panel_sha256": digest,
        "source_panel_rows": len(all_rows),
        "balanced_2000_2019_2023_n": len(balanced),
        "median_g_2000_2019": statistics.median(a),
        "median_g_2000_2023": statistics.median(c),
        "difference_of_separate_medians": statistics.median(c) - statistics.median(a),
        "median_of_country_paired_differences": statistics.median(d),
        "mean_of_country_paired_differences": statistics.mean(d),
        "paired_negative_count": sum(x < 0 for x in d),
        "paired_positive_count": sum(x > 0 for x in d),
        "paired_zero_count": sum(x == 0 for x in d),
        "country_growth_sign_changes_across_horizons": sum(x["sign_changes_between_horizons"] for x in balanced),
        "leave_one_country_out_paired_median_min": min(leave_one_out),
        "leave_one_country_out_paired_median_max": max(leave_one_out),
        "country_level_rows": balanced,
        "design": "within-2026-release, two-endpoint-horizon comparison; post hoc descriptive",
        "not_historical_vintage_revision": True,
        "independent_ilo_employment_validated": False,
        "publication_gate": "MAJOR_REVISION_NO_SUBMISSION",
    }
    if sum((report["paired_negative_count"],report["paired_positive_count"],report["paired_zero_count"])) != len(balanced):
        raise AssertionError("Paired sign-count reconciliation failed")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    summary = {k:v for k,v in report.items() if k!="country_level_rows"}
    print(json.dumps(summary, indent=2))
    return report

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", required=True, type=pathlib.Path)
    p.add_argument("--out", required=True, type=pathlib.Path)
    args = p.parse_args()
    run(args.panel,args.out)

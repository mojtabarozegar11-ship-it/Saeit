#!/usr/bin/env python3
"""AE-2026-001: empirical 73-country ILOSTAT/WDI worker-growth cohort audit.

Reads the previously executed source-locked 73-country comparison and the
archived 2026 WDI productivity panel. Estimates descriptive country-level
bootstrap intervals (not causal, not vintage-specific, not representative).
No download, imputation, p-hacking, or fake independent data.
"""
import argparse
import csv
import hashlib
import json
import math
import pathlib
import random
import statistics

SEED = 20261026
BOOTSTRAPS = 6000
ENDPOINT_YEARS = 19

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def percentile(values, p):
    s = sorted(values)
    i = (len(s)-1)*p
    a = int(i)
    return s[a] + (s[min(a+1,len(s)-1)]-s[a])*(i-a)

def boot_median(values, rng, iterations=BOOTSTRAPS):
    if not values:
        raise ValueError("Empty bootstrap group")
    n = len(values)
    draws = [statistics.median(values[rng.randrange(n)] for _ in range(n))
             for _ in range(iterations)]
    return [percentile(draws,0.025), percentile(draws,0.975)]

def bootstrap_difference(a, b, rng, iterations=BOOTSTRAPS):
    if not a or not b:
        raise ValueError("Both groups required")
    na, nb = len(a), len(b)
    draws = []
    for _ in range(iterations):
        aa = [a[rng.randrange(na)] for j in range(na)]
        bb = [b[rng.randrange(nb)] for j in range(nb)]
        draws.append(statistics.median(aa)-statistics.median(bb))
    return [percentile(draws,0.025),percentile(draws,0.975)]

def run(growth_path, panel_path, out):
    source = json.loads(growth_path.read_text(encoding="utf-8"))
    rows = source["country_rows"]
    if source.get("two_endpoint_countries_n") != 73 or len(rows)!=73:
        raise ValueError("Unexpected growth source cohort size")
    if source.get("wdi_revision_causality_identified") is not False:
        raise ValueError("Source must explicitly reject WDI historical causality")
    countries = [r["country_iso3"] for r in rows]
    if len(set(countries))!=73:
        raise ValueError("Duplicate country in growth source")
    stable = [r for r in rows if r["same_ilostat_source"]]
    changed = [r for r in rows if not r["same_ilostat_source"]]
    if len(stable)!=60 or len(changed)!=13:
        raise ValueError("Source-code stability groups changed")
    for row in rows:
        x = float(row["absolute_growth_difference"])
        y = abs(float(row["signed_growth_difference"]))
        if not (math.isfinite(x) and x>=0 and abs(x-y)<1e-12):
            raise ValueError("Invalid signed/absolute growth discrepancy")
        if not (math.isfinite(row["annual_ilo_employment_log_growth"])
                and math.isfinite(row["annual_wdi_implied_employment_log_growth"])):
            raise ValueError("Invalid employment growth")
    rng = random.Random(SEED)
    all_abs = [r["absolute_growth_difference"] for r in rows]
    stable_abs = [r["absolute_growth_difference"] for r in stable]
    changed_abs = [r["absolute_growth_difference"] for r in changed]
    wdi_growth = {}
    with panel_path.open(encoding="utf-8-sig",newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            iso = r["country_iso3"].strip()
            if iso in wdi_growth:
                raise ValueError("Duplicate WDI ISO3 country")
            try:
                p0=float(r["ag_value_added_per_worker_2000_constant2015usd"])
                p1=float(r["ag_value_added_per_worker_2019_constant2015usd"])
            except (ValueError,TypeError):
                continue
            if all(math.isfinite(v) and v>0 for v in (p0,p1)):
                wdi_growth[iso]=math.log(p1/p0)/ENDPOINT_YEARS
    selected = sorted(set(countries)&set(wdi_growth))
    if len(selected)!=73:
        raise ValueError("Not all source-locked 73 countries in WDI productivity panel")
    nonselected = sorted(set(wdi_growth)-set(selected))
    if not nonselected:
        raise ValueError("No unmatched WDI countries to assess selection")
    matched_growth=[wdi_growth[c] for c in selected]
    other_growth=[wdi_growth[c] for c in nonselected]
    sign_sensitivity=[]
    for threshold in (0.0,0.001,0.0025,0.005):
        eligible=[r for r in rows if min(abs(r["annual_ilo_employment_log_growth"]),
                                       abs(r["annual_wdi_implied_employment_log_growth"]))>threshold]
        sign_sensitivity.append({
            "annual_log_growth_threshold":threshold,
            "eligible_countries_n":len(eligible),
            "sign_disagreement_n":sum(r["growth_sign_disagreement"] for r in eligible),
        })
    leave_one_out=[statistics.median(all_abs[:i]+all_abs[i+1:]) for i in range(len(all_abs))]
    result={
        "study":"AE-2026-001 original matched-country selection and country-level uncertainty",
        "growth_artifact_sha256":sha256(growth_path),
        "archived_wdi_panel_sha256":sha256(panel_path),
        "seed":SEED,
        "country_bootstrap_resamples":BOOTSTRAPS,
        "worker_growth_comparison_countries":len(rows),
        "source_stable_n":len(stable),
        "source_changed_n":len(changed),
        "absolute_worker_growth_discrepancy_median_log_per_year":statistics.median(all_abs),
        "absolute_worker_growth_discrepancy_bootstrap_95pct":boot_median(all_abs,rng),
        "stable_source_median_absolute_discrepancy":statistics.median(stable_abs),
        "changed_source_median_absolute_discrepancy":statistics.median(changed_abs),
        "changed_minus_stable_median_discrepancy":statistics.median(changed_abs)-statistics.median(stable_abs),
        "changed_minus_stable_bootstrap_95pct":bootstrap_difference(changed_abs,stable_abs,rng),
        "leave_one_country_out_median_range":[min(leave_one_out),max(leave_one_out)],
        "growth_sign_disagreement_threshold_sensitivity":sign_sensitivity,
        "wdi_2026_positive_two_endpoint_countries_n":len(wdi_growth),
        "matched_countries_n":len(selected),
        "unmatched_countries_n":len(nonselected),
        "matched_wdi_productivity_growth_median":statistics.median(matched_growth),
        "unmatched_wdi_productivity_growth_median":statistics.median(other_growth),
        "matched_minus_unmatched_wdi_productivity_growth_median":
            statistics.median(matched_growth)-statistics.median(other_growth),
        "matched_country_codes":selected,
        "unmatched_country_codes":nonselected,
        "interpretation":"Descriptive nonrandom cohort selection and country-level resampling. Bootstrap intervals reflect observed-country sampling sensitivity only, not WDI historical-vintage causality or independent surveys.",
        "independent_historical_ilo_vintages_verified":False,
        "causal_historical_vintage_inference":False,
        "publication_gate":"MAJOR_REVISION_NO_SUBMISSION"
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if not k.endswith("_country_codes")},indent=2))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--growth-json",required=True,type=pathlib.Path)
    p.add_argument("--wdi-panel",required=True,type=pathlib.Path)
    p.add_argument("--out",required=True,type=pathlib.Path)
    a=p.parse_args()
    run(a.growth_json,a.wdi_panel,a.out)

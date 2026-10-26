#!/usr/bin/env python3
"""AE-2026-001: original-country regional selection audit, not causal inference.

Inputs are a SHA256-locked archived 2026 WDI country panel and the original
73-country current-source ILOSTAT/WDI growth comparison. All units are countries.
No imputation, independent-vintage attribution, or journal-readiness claim.
"""
import argparse,csv,hashlib,json,math,pathlib,random,statistics
from collections import Counter,defaultdict

PANEL_SHA="715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169"
GROWTH_SHA="3feee3649062338bc55489019791cbddde608714eb4ab7837dde486f710c28a8"
SEED=20261026
PERMUTATIONS=10000

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def chisq(groups,selected):
    n=sum(groups.values()); k=sum(selected.values())
    if not (0<k<n):raise ValueError("Invalid cohort size")
    s=0.
    for group,total in groups.items():
        a=selected[group]; b=total-a
        if not (0<=a<=total):raise ValueError("Invalid regional allocation")
        ea=total*k/n; eb=total*(n-k)/n
        s+=(a-ea)**2/ea+(b-eb)**2/eb
    return s

def run(growth_file,panel_file,out):
    if sha(growth_file)!=GROWTH_SHA:raise ValueError("Source growth JSON SHA256 mismatch")
    if sha(panel_file)!=PANEL_SHA:raise ValueError("Source WDI panel SHA256 mismatch")
    src=json.loads(growth_file.read_text(encoding="utf-8"))
    rows=src["country_rows"]
    if src.get("two_endpoint_countries_n")!=73 or len(rows)!=73:
        raise ValueError("Unexpected original 73-country growth cohort")
    if src.get("wdi_revision_causality_identified") is not False:
        raise ValueError("Historical causal claims not permitted")
    selected=[r["country_iso3"] for r in rows]
    if len(set(selected))!=73:raise ValueError("Duplicate source country")
    panel={}
    with panel_file.open(encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):
            c=row["country_iso3"].strip()
            if c in panel:raise ValueError("Duplicate WDI country")
            try:
                p0=float(row["ag_value_added_per_worker_2000_constant2015usd"])
                p1=float(row["ag_value_added_per_worker_2019_constant2015usd"])
            except (TypeError,ValueError):continue
            if not (math.isfinite(p0) and math.isfinite(p1) and p0>0 and p1>0):continue
            region=row["region"].strip() or "Unspecified"
            panel[c]=(region,math.log(p1/p0)/19)
    if len(panel)!=157 or not set(selected).issubset(panel):
        raise ValueError("Original 157/73 country intersection changed")
    regions=Counter(v[0] for v in panel.values())
    sel_regions=Counter(panel[c][0] for c in selected)
    actual=chisq(regions,sel_regions)
    rng=random.Random(SEED)
    country_codes=sorted(panel)
    more_extreme=0
    for _ in range(PERMUTATIONS):
        sampled=rng.sample(country_codes,len(selected))
        if chisq(regions,Counter(panel[c][0] for c in sampled))>=actual-1e-12:
            more_extreme+=1
    by_region=defaultdict(lambda:{"matched":[],"unmatched":[]})
    selected_set=set(selected)
    for c,(reg,growth) in panel.items():
        by_region[reg]["matched" if c in selected_set else "unmatched"].append(growth)
    summary=[]
    for region in sorted(by_region):
        matched=by_region[region]["matched"];other=by_region[region]["unmatched"]
        summary.append({
            "region":region,"total_economies":len(matched)+len(other),
            "matched_economies":len(matched),"unmatched_economies":len(other),
            "coverage_share":len(matched)/(len(matched)+len(other)),
            "matched_median_annual_log_productivity_growth":statistics.median(matched) if matched else None,
            "unmatched_median_annual_log_productivity_growth":statistics.median(other) if other else None
        })
    result={
        "study":"AE-2026-001 regional composition of current-source employment-matched WDI cohort",
        "growth_artifact_sha256":sha(growth_file),
        "wdi_2026_panel_sha256":sha(panel_file),
        "n_wdi_positive_endpoints":len(panel),"n_matched":len(selected),
        "n_unmatched":len(panel)-len(selected),
        "regions":summary,"region_coverage_chi_square":actual,
        "region_coverage_cramers_v":math.sqrt(actual/len(panel)),
        "conditional_random_label_permutation_n":PERMUTATIONS,
        "permutation_seed":SEED,
        "region_coverage_permutation_p":(more_extreme+1)/(PERMUTATIONS+1),
        "inference_note":"Permutation conditions on the observed nonrandom 157-country panel and is a descriptive exchangeability diagnostic, not a probability-sample test of global representativeness.",
        "historical_ilo_2024_2025_vintages_verified":False,
        "historical_wdi_revision_causality_identified":False,
        "publication_gate":"MAJOR_REVISION_NO_SUBMISSION"
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--growth-json",type=pathlib.Path,required=True)
    p.add_argument("--wdi-panel",type=pathlib.Path,required=True)
    p.add_argument("--out",type=pathlib.Path,required=True)
    a=p.parse_args()
    run(a.growth_json,a.wdi_panel,a.out)

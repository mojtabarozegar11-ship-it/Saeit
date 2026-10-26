#!/usr/bin/env python3
"""Source-locked ILOSTAT employment coverage, not a WDI vintage/causal validation.

Inputs: original ILOSTAT EMP_TEMP_SEX_ECO_NB_A RDS-derived 2000/2019
unfiltered CSV and source-hashed 2026 WDI per-worker panel. The ILOSTAT
aggregate agriculture code is used without mixing ISIC Rev3 A+B/Rev4 A.
"""
import argparse,csv,hashlib,json,math,pathlib,statistics
from collections import Counter,defaultdict

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def run(ilo,wdi,out):
    with ilo.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        expected={"ref_area","source","indicator","sex","classif1","time","obs_value","best_source"}
        if not expected.issubset(reader.fieldnames or []):raise ValueError("ILOSTAT schema mismatch")
        rows=list(reader)
    if not rows:raise ValueError("Empty ILOSTAT source")
    indicator_codes={row["indicator"].strip() for row in rows if row["indicator"].strip()}
    if len(indicator_codes)!=1 or not next(iter(indicator_codes)).startswith("EMP_TEMP_SEX_ECO_NB"):
        raise ValueError("Unexpected mixed or non-employment indicator codes: "+repr(indicator_codes))
    candidates=defaultdict(list)
    for row in rows:
        if row["sex"]!="SEX_T" or row["classif1"]!="ECO_AGGREGATE_AGR":continue
        if str(row["best_source"]).strip() not in ("1","1.0","True","TRUE"):continue
        year=row["time"].strip()
        if year not in ("2000","2019"):continue
        country=row["ref_area"].strip()
        if not country:continue
        try:val=float(row["obs_value"])
        except (TypeError,ValueError):continue
        if not math.isfinite(val) or val<0:raise ValueError("Invalid employment count")
        candidates[(country,year)].append({"country_iso3":country,"year":int(year),
            "agricultural_employment_thousands":val,"agricultural_employment_persons":val*1000,
            "source":row["source"].strip()})
    ambiguous={k:v for k,v in candidates.items() if len(v)!=1}
    observed={k:v[0] for k,v in candidates.items() if len(v)==1}
    with wdi.open(encoding="utf-8-sig",newline="") as f:
        wdirows=list(csv.DictReader(f))
    valid_wdi=set()
    for r in wdirows:
        try:
            p=float(r["ag_value_added_per_worker_2000_constant2015usd"])
            q=float(r["ag_value_added_per_worker_2019_constant2015usd"])
        except (TypeError,ValueError):continue
        if p>0 and q>0 and math.isfinite(p) and math.isfinite(q):
            valid_wdi.add(r["country_iso3"])
    both_ilo=sorted(c for c in {c for c,y in observed} if (c,"2000") in observed and (c,"2019") in observed)
    matched=sorted(set(both_ilo)&valid_wdi)
    source_changed=[c for c in both_ilo if observed[(c,"2000")]["source"]!=observed[(c,"2019")]["source"]]
    stable=[c for c in matched if c not in source_changed]
    output={
        "ilostat_source_endpoint_csv_sha256":sha(ilo),
        "wdi_2026_panel_sha256":sha(wdi),
        "indicator":next(iter(indicator_codes)),
        "source_dataset_id":"EMP_TEMP_SEX_ECO_NB_A",
        "sex":"SEX_T",
        "economic_activity":"ECO_AGGREGATE_AGR",
        "best_source":"1",
        "unit":"thousands of employed persons; converted to persons x1000",
        "input_endpoint_rows_all_categories":len(rows),
        "eligible_country_year_candidates":len(candidates),
        "ambiguous_duplicate_country_years_excluded":len(ambiguous),
        "unambiguous_country_year_observations":len(observed),
        "observed_2000":sum(y=="2000" for c,y in observed),
        "observed_2019":sum(y=="2019" for c,y in observed),
        "ilostat_both_endpoints_n":len(both_ilo),
        "wdi_2026_positive_pair_n":len(valid_wdi),
        "intersection_both_endpoints_n":len(matched),
        "matched_country_codes":matched,
        "source_changed_between_2000_2019_n":len(source_changed),
        "matched_source_stable_n":len(stable),
        "source_stability_not_equivalent_to_vintage_comparability":True,
        "independent_wdi_worker_denominator_reconciliation":False,
        "historical_ilostat_2024_2025_vintages_verified":False,
        "publication_gate":"MAJOR_REVISION_NO_SUBMISSION",
        "ambiguous_country_years":[{"country":c,"year":y,"rows":len(v)} for (c,y),v in sorted(ambiguous.items())],
        "country_year_observations":[observed[k] for k in sorted(observed)]
    }
    if not observed:raise ValueError("No official absolute agriculture employment observations")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(output,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:v for k,v in output.items() if k not in ("country_year_observations","matched_country_codes","ambiguous_country_years")},indent=2))
    return output

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--ilostat-csv",type=pathlib.Path,required=True)
    p.add_argument("--wdi-panel",type=pathlib.Path,required=True)
    p.add_argument("--out",type=pathlib.Path,required=True)
    a=p.parse_args()
    run(a.ilostat_csv,a.wdi_panel,a.out)

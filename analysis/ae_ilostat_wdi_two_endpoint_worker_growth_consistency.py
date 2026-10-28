#!/usr/bin/env python3
"""Independent-source worker growth consistency, NOT WDI vintage causality.

Input: source-locked 2000/2019 ILOSTAT/WDI worker-level audit JSON.
One observation per matched country with BOTH endpoints; separate
same-ILOSTAT-source and changed-source groups. No p-values or imputation.
"""
import argparse,hashlib,json,math,pathlib,statistics
from collections import defaultdict

def audit(source,out):
    data=json.loads(source.read_text(encoding="utf-8"))
    if data.get("independent_ilo_level_comparison_completed") is not True:
        raise ValueError("Source-level audit incomplete")
    if data.get("wdi_historical_revision_causality_identified") is not False:
        raise ValueError("Source incorrectly claims historical causality")
    grouped=defaultdict(dict)
    for row in data["country_year_rows"]:
        country=row["country_iso3"];year=int(row["year"])
        if year in grouped[country]:raise ValueError("Duplicate country-year")
        grouped[country][year]=row
    both=[]
    for country,yrs in sorted(grouped.items()):
        if set(yrs)!={2000,2019}:continue
        a,b=yrs[2000],yrs[2019]
        x0,x1=a["ilostat_absolute_workers_persons"],b["ilostat_absolute_workers_persons"]
        y0,y1=a["wdi_implied_workers_persons"],b["wdi_implied_workers_persons"]
        if min(x0,x1,y0,y1)<=0:raise ValueError("Nonpositive matched worker count")
        g_ilo=math.log(x1/x0)/19
        g_wdi=math.log(y1/y0)/19
        both.append({
            "country_iso3":country,"ilostat_source_2000":a["ilostat_source"],
            "ilostat_source_2019":b["ilostat_source"],
            "same_ilostat_source":a["ilostat_source"]==b["ilostat_source"],
            "annual_ilo_employment_log_growth":g_ilo,
            "annual_wdi_implied_employment_log_growth":g_wdi,
            "signed_growth_difference":g_ilo-g_wdi,
            "absolute_growth_difference":abs(g_ilo-g_wdi),
            "growth_sign_disagreement":(g_ilo>0)!=(g_wdi>0),
        })
    if not both:raise ValueError("No two-endpoint country pairs")
    stable=[r for r in both if r["same_ilostat_source"]]
    changed=[r for r in both if not r["same_ilostat_source"]]
    def summary(rows):
        return {
            "n":len(rows),
            "median_absolute_annual_log_growth_difference":statistics.median(r["absolute_growth_difference"] for r in rows) if rows else None,
            "median_signed_annual_log_growth_difference":statistics.median(r["signed_growth_difference"] for r in rows) if rows else None,
            "growth_sign_disagreements_n":sum(r["growth_sign_disagreement"] for r in rows)
        }
    result={
        "input_worker_level_artifact_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "two_endpoint_countries_n":len(both),
        "all_two_endpoint_countries":summary(both),
        "same_ilostat_source_countries":summary(stable),
        "changed_ilostat_source_countries":summary(changed),
        "country_rows":both,
        "comparison":"2000-to-2019 annual log worker growth from two currently retrieved source families",
        "independent_historical_2024_2025_employment_vintage_validated":False,
        "wdi_revision_causality_identified":False,
        "publication_gate":"MAJOR_REVISION_NO_SUBMISSION"
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="country_rows"},indent=2))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source-json",type=pathlib.Path,required=True)
    p.add_argument("--out",type=pathlib.Path,required=True)
    a=p.parse_args()
    audit(a.source_json,a.out)

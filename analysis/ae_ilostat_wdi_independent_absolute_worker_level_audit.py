#!/usr/bin/env python3
"""AE: actual independent ILOSTAT absolute agriculture workers vs WDI implied L*.

CURRENT-SOURCE LEVEL PLAUSIBILITY ONLY: NOT historical 2024/25 vintage
attribution, causal identification, or proof that ILO survey counts equal
the modelled WDI denominator. Download original WDI numerator from API.
"""
import argparse,hashlib,json,math,pathlib,statistics,urllib.request,csv
from collections import defaultdict

URL="https://api.worldbank.org/v2/country/all/indicator/NV.AGR.TOTL.KD?format=json&date=2000%3A2019&per_page=20000"
LIMIT=12_000_000

def digest(data):return hashlib.sha256(data).hexdigest()

def download(url):
    req=urllib.request.Request(url,headers={"User-Agent":"AE-2026-001 academic source audit (noncommercial, one request)"})
    with urllib.request.urlopen(req,timeout=75) as f:
        chunks=[];size=0
        while True:
            part=f.read(65536)
            if not part:break
            size+=len(part)
            if size>LIMIT:raise ValueError("WDI response exceeds safe size limit")
            chunks.append(part)
    return b"".join(chunks)

def run(ilo_path,panel_path,out):
    ilodata=json.loads(ilo_path.read_text(encoding="utf-8"))
    if ilodata.get("source_dataset_id")!="EMP_TEMP_SEX_ECO_NB_A" or ilodata.get("economic_activity")!="ECO_AGGREGATE_AGR":
        raise ValueError("Wrong ILO source dataset/sector")
    if ilodata.get("ambiguous_duplicate_country_years_excluded")!=0:
        raise ValueError("Ambiguous ILO country-year sources remain")
    source=download(URL)
    payload=json.loads(source.decode("utf-8"))
    if not isinstance(payload,list) or len(payload)!=2 or not isinstance(payload[1],list):
        raise ValueError("WDI API structure unexpected")
    meta=payload[0]
    if int(meta.get("pages",0))!=1:raise ValueError("WDI API pagination incomplete")
    numerator={}
    for row in payload[1]:
        if row.get("indicator",{}).get("id")!="NV.AGR.TOTL.KD":continue
        iso=str(row.get("countryiso3code") or "").strip()
        year=str(row.get("date") or "")
        if len(iso)!=3 or year not in ("2000","2019"):continue
        try:v=float(row.get("value"))
        except (ValueError,TypeError):continue
        if not math.isfinite(v) or v<=0:continue
        key=(iso,year)
        if key in numerator:raise ValueError("Duplicate WDI numerator")
        numerator[key]=v
    with panel_path.open(encoding="utf-8-sig",newline="") as f:
        panel=list(csv.DictReader(f))
    per_worker={}
    for row in panel:
        iso=row["country_iso3"]
        for year in ("2000","2019"):
            key=f"ag_value_added_per_worker_{year}_constant2015usd"
            try:v=float(row[key])
            except (ValueError,TypeError):continue
            if math.isfinite(v) and v>0:per_worker[(iso,year)]=v
    ilo={(r["country_iso3"],str(r["year"])):r for r in ilodata["country_year_observations"]}
    matched=[]
    for key in sorted(set(ilo)&set(per_worker)&set(numerator)):
        workers_implied=numerator[key]/per_worker[key]
        workers_ilo=ilo[key]["agricultural_employment_persons"]
        if not (workers_implied>0 and workers_ilo>0):continue
        ratio=workers_ilo/workers_implied
        matched.append({
            "country_iso3":key[0],"year":int(key[1]),
            "wdi_numerator_constant2015usd":numerator[key],
            "wdi_per_worker_constant2015usd":per_worker[key],
            "wdi_implied_workers_persons":workers_implied,
            "ilostat_absolute_workers_persons":workers_ilo,
            "ilostat_source":ilo[key]["source"],
            "ilostat_to_wdi_implied_worker_ratio":ratio,
            "absolute_log_ratio":abs(math.log(ratio)),
            "absolute_relative_difference":abs(ratio-1)
        })
    if not matched:raise ValueError("No independently matched positive country-year records")
    grouped=defaultdict(dict)
    for r in matched:grouped[r["country_iso3"]][r["year"]]=r
    complete=sorted(c for c,yrs in grouped.items() if set(yrs)=={2000,2019})
    stable=sorted(c for c in complete if grouped[c][2000]["ilostat_source"]==grouped[c][2019]["ilostat_source"])
    abslogs=[r["absolute_log_ratio"] for r in matched]
    outobj={
        "study":"AE-2026-001 independent current-source worker-count level plausibility",
        "wdi_numerator_api_url":URL,
        "wdi_numerator_api_sha256":digest(source),
        "wdi_numerator_api_lastupdated":meta.get("lastupdated"),
        "wdi_numerator_response_bytes":len(source),
        "wdi_numerator_positive_endpoint_records":len(numerator),
        "wdi_per_worker_panel_sha256":hashlib.sha256(panel_path.read_bytes()).hexdigest(),
        "ilostat_coverage_json_sha256":hashlib.sha256(ilo_path.read_bytes()).hexdigest(),
        "ilostat_dataset":"EMP_TEMP_SEX_ECO_NB_A",
        "ilostat_activity":"ECO_AGGREGATE_AGR",
        "matched_positive_country_years_n":len(matched),
        "matched_country_codes_n":len(grouped),
        "countries_both_years_n":len(complete),
        "countries_both_years_same_ilostat_source_n":len(stable),
        "median_absolute_log_ilo_to_implied_worker_ratio":statistics.median(abslogs),
        "median_absolute_relative_ilo_to_implied_worker_difference":statistics.median(r["absolute_relative_difference"] for r in matched),
        "within_10pct_count":sum(r["absolute_relative_difference"]<=.10 for r in matched),
        "within_25pct_count":sum(r["absolute_relative_difference"]<=.25 for r in matched),
        "within_50pct_count":sum(r["absolute_relative_difference"]<=.50 for r in matched),
        "country_year_rows":matched,
        "same_2024_2025_ilo_vintages_verified":False,
        "independent_ilo_level_comparison_completed":True,
        "wdi_historical_revision_causality_identified":False,
        "publication_gate":"MAJOR_REVISION_NO_SUBMISSION"
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(outobj,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:v for k,v in outobj.items() if k!="country_year_rows"},indent=2))
    return outobj

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--ilo-coverage-json",type=pathlib.Path,required=True)
    p.add_argument("--wdi-panel",type=pathlib.Path,required=True)
    p.add_argument("--out",type=pathlib.Path,required=True)
    a=p.parse_args()
    run(a.ilo_coverage_json,a.wdi_panel,a.out)

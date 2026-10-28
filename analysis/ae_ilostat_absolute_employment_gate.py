#!/usr/bin/env python3
"""Fail-closed ILOSTAT absolute-employment source audit for AE-2026-001.

Usage: python analysis/ae_ilostat_absolute_employment_gate.py --csv FILE --metadata JSON --out REPORT.json
Metadata JSON requires source_url, retrieved_utc, release_date, indicator_code,
unit, classification, country_column, year_column, value_column, activity_column,
sex_column, agricultural_activity_value, total_sex_value, and sha256.
No network access, imputation, or claims about vintage matching.
"""
import argparse,csv,hashlib,json,math,pathlib,sys
from collections import Counter
REQUIRED=("source_url","retrieved_utc","release_date","indicator_code","unit","classification",
"country_column","year_column","value_column","activity_column","sex_column",
"agricultural_activity_value","total_sex_value","sha256")
def audit(csv_path, meta):
    missing=[k for k in REQUIRED if not str(meta.get(k,"")).strip()]
    if missing: raise ValueError("Missing metadata: "+", ".join(missing))
    if not str(meta["source_url"]).startswith("https://"): raise ValueError("Source URL must be HTTPS")
    if str(meta["unit"]).strip().lower() not in ("thousands","thousand persons","1000 persons"):
        raise ValueError("Absolute employment must be in thousands of persons, not a share")
    digest=hashlib.sha256(csv_path.read_bytes()).hexdigest()
    if digest.lower()!=str(meta["sha256"]).lower(): raise ValueError("SHA256 mismatch")
    years={2000,2019}
    records={}
    with csv_path.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        cols=[meta[k] for k in ("country_column","year_column","value_column","activity_column","sex_column")]
        if not set(cols).issubset(reader.fieldnames or []): raise ValueError("Required CSV columns absent")
        for row in reader:
            if row[meta["activity_column"]]!=meta["agricultural_activity_value"] or row[meta["sex_column"]]!=meta["total_sex_value"]:continue
            try: year=int(row[meta["year_column"]])
            except (TypeError,ValueError):continue
            if year not in years:continue
            country=row[meta["country_column"]].strip()
            if not country:continue
            try: value=float(row[meta["value_column"]])
            except (TypeError,ValueError):continue
            if not math.isfinite(value) or value<0:raise ValueError("Invalid employment count")
            key=(country,year)
            if key in records:raise ValueError("Duplicate country/year after filters: "+repr(key))
            records[key]=value
    countries={c for c,y in records}
    complete=sorted(c for c in countries if all((c,y) in records for y in years))
    return {"status":"source_file_audited_not_vintage_matched","sha256":digest,
            "release_date":meta["release_date"],"indicator_code":meta["indicator_code"],
            "countries_any_endpoint":len(countries),"countries_both_endpoints":len(complete),
            "year_2000_observations":sum(y==2000 for c,y in records),
            "year_2019_observations":sum(y==2019 for c,y in records),
            "complete_country_codes":complete,
            "independent_wdi_comparison_completed":False,
            "historical_2024_2025_vintages_verified":False,
            "publication_gate":"BLOCKED"}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv",type=pathlib.Path,required=True)
    p.add_argument("--metadata",type=pathlib.Path,required=True)
    p.add_argument("--out",type=pathlib.Path,required=True)
    a=p.parse_args()
    try:
        report=audit(a.csv,json.loads(a.metadata.read_text(encoding="utf-8")))
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as exc:
        print("FAIL CLOSED:",exc,file=sys.stderr);return 2
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="complete_country_codes"},indent=2))
    return 0
if __name__=="__main__":sys.exit(main())

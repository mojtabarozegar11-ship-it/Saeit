#!/usr/bin/env python3
"""Official WDI 2024/2025/2026 fixed-country cohort sensitivity audit.

Prevents the incorrect inference that sign-flip changes across 2024/2026 and
2025/2026 samples are due only to archive age. Reuses the source-verified
historical XLSX parser. No simulated country values, imputation or inference.
The old archives are downloaded only into an ephemeral free GitHub runner.
"""
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
SOURCE=HERE/"official_wdi_2024_vs_2026_vintage_audit.py"
PANEL=ROOT/"AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv"
OUT=ROOT/"AE-2026-001_THREE_VINTAGE_FIXED_COHORT_AUDIT_2026-10-26.json"
ARCHIVES={
  "2024":"https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_excel_2024_10_24.zip",
  "2025":"https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_excel_2025_10_08.zip",
}
EXPECTED_SHA={
  "2024":"5a8922c6629eea69b93a314ebb2363ed8d5faf4f345ff19dbe203c62692af5a1",
  "2025":"9185df6f3029ca6c990d87674dcec60e4633cf0b344bc4ee6459392f1cfdc173",
}
spec=importlib.util.spec_from_file_location("wdi_original_vintage",SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def positive(row,year):
    return m.maybe_pos(row.get(str(year)))

def growth(row,year):
    a,b=positive(row,2000),positive(row,year)
    return math.log(b/a)/(year-2000) if a is not None and b is not None else None

def get_latest():
    result={}
    with PANEL.open(newline="",encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            iso=row["country_iso3"]
            if iso in result:
                raise RuntimeError("Duplicate 2026 economy "+iso)
            result[iso]={str(y):m.maybe_pos(row[m.COLUMN[y]]) for y in m.YEARS}
    if len(result)!=217:
        raise RuntimeError("2026 nonaggregate country set must equal 217")
    return result

def get_old():
    old={}
    provenance={}
    with tempfile.TemporaryDirectory(prefix="wdi_three_vintage_") as d:
        tmp=Path(d)
        for vintage,url in ARCHIVES.items():
            m.ARCHIVE=url
            meta=m.fetch_archive(tmp/(vintage+".zip"))
            if meta["sha256"]!=EXPECTED_SHA[vintage]:
                raise RuntimeError(f"Official {vintage} archive SHA changed; no silent replacement")
            old[vintage],sheets=m.load_original_wdi_excel(tmp/(vintage+".zip"),tmp)
            provenance[vintage]={**meta,"sheets_inspected":sheets,"indicator":m.INDICATOR}
            (tmp/(vintage+".zip")).unlink()
    return old,provenance

def stats(values):
    return {"n":len(values),"median":statistics.median(values) if values else None,
            "mean":statistics.mean(values) if values else None}

def main():
    now=get_latest()
    old,meta=get_old()
    datasets={**old,"2026":now}
    three_way=sorted(set.intersection(*(set(x) for x in datasets.values())))
    report={
        "source":"World Bank WDI historical XLSX archive, same constant-2015 USD/worker indicator NV.AGR.EMPL.KD",
        "country_panel_2026_sha256":hashlib.sha256(PANEL.read_bytes()).hexdigest(),
        "archive_provenance":meta,
        "same_country_2000_2019":{},
        "same_country_2000_2023":{},
        "limitations":[
            "All comparisons are unweighted by economy and descriptive; no causality, significance or proof of novel publication contribution.",
            "2024 archive lacks a comparable 2023 observation; 2000–2023 cannot have a three-vintage common cohort.",
            "A shared country cohort removes country-composition confounding but cannot resolve statistical revision causes or time-dependent definitions.",
            "Archives must match the prior observed SHA256; otherwise computation fails rather than substituting files."
        ]
    }
    for end in (2019,2023):
        rates={v:{iso:growth(row,end) for iso,row in dat.items()} for v,dat in datasets.items()}
        cohort=[iso for iso in three_way if all(rates[v].get(iso) is not None for v in datasets)]
        d={"cohort_n":len(cohort),"iso3":cohort,"vintage_summary":{},"pairwise_revisions":{}}
        for v in datasets:
            d["vintage_summary"][v]=stats([rates[v][iso] for iso in cohort])
        for a,b in (("2024","2025"),("2025","2026"),("2024","2026")):
            delta=[rates[b][iso]-rates[a][iso] for iso in cohort]
            d["pairwise_revisions"][a+"_to_"+b]={
                "same_cohort_n":len(cohort),
                "median_annual_growth_revision":statistics.median(delta) if delta else None,
                "sign_changes":sum((rates[a][iso]>0)!=(rates[b][iso]>0) for iso in cohort),
                "changed_country_codes":[iso for iso in cohort if (rates[a][iso]>0)!=(rates[b][iso]>0)]
            }
        d["country_level_rates"]=[
            {"iso3":iso,**{v:rates[v][iso] for v in datasets}}
            for iso in cohort
        ]
        report["same_country_2000_"+str(end)]=d
    if report["same_country_2000_2019"]["cohort_n"]<100:
        raise RuntimeError("Insufficient common-country cohort for credible 2000–2019 descriptive comparison")
    if report["same_country_2000_2023"]["cohort_n"]!=0:
        raise RuntimeError("2024 historical 2023 availability unexpectedly changed; re-audit assumptions")
    report["quality_gate"]={
        "fixed_country_comparison_for_2000_2019":"PASS",
        "three_vintage_2000_2023":"NOT_ESTIMABLE_SOURCE_MISSING",
        "publication_novelty":"NOT_ESTABLISHED"
    }
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("archive_provenance","limitations")},indent=2))

if __name__=="__main__":main()

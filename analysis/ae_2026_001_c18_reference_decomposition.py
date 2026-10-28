#!/usr/bin/env python3
"""C18: alternative-reference regional shift-share on source-locked WDI panel."""
import csv, hashlib, json, math
from pathlib import Path
from statistics import mean
SRC = Path("research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv")
HASH = "715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169"
if hashlib.sha256(SRC.read_bytes()).hexdigest() != HASH:
    raise SystemExit("Source hash mismatch")
rows = []
with SRC.open(encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        try:
            p19, p23 = float(r["ag_value_added_per_worker_2019_constant2015usd"]), float(r["ag_value_added_per_worker_2023_constant2015usd"])
            p00 = float(r["ag_value_added_per_worker_2000_constant2015usd"]) if r["ag_value_added_per_worker_2000_constant2015usd"] else None
            if p19 > 0 and p23 > 0 and math.isfinite(p19) and math.isfinite(p23):
                rows.append(dict(iso=r["country_iso3"], region=r["region"].strip(), baseline=p00 is not None and p00 > 0 and math.isfinite(p00), g=25*math.log(p23/p19)))
        except ValueError:
            continue
B = [r for r in rows if r["baseline"]]
A = [r for r in rows if not r["baseline"]]
if (len(B),len(A)) != (153,16): raise SystemExit("Unexpected cohorts")
def compute(P):
    regions = sorted(set(r["region"] for r in B))
    base_c = base_w = pooled_c = pooled_w = 0.0
    for region in regions:
        br = [r["g"] for r in B if r["region"] == region]
        pr = [r["g"] for r in P if r["region"] == region]
        wb,wp = len(br)/len(B),len(pr)/len(P)
        mb,mp = mean(br),mean(pr)
        base_c += (wp-wb)*mb
        base_w += wp*(mp-mb)
        pooled_c += (wp-wb)*mp
        pooled_w += wb*(mp-mb)
    gap = mean(r["g"] for r in P)-mean(r["g"] for r in B)
    if not all(math.isclose(x,gap,abs_tol=1e-11) for x in (base_c+base_w,pooled_c+pooled_w)):
        raise SystemExit("Reference identity failed")
    return dict(n=len(P),gap=gap,baseline=dict(composition=base_c,within=base_w),
                pooled=dict(composition=pooled_c,within=pooled_w),
                symmetric=dict(composition=(base_c+pooled_c)/2,within=(base_w+pooled_w)/2))
out = dict(source_sha256=HASH,all_169=compute(rows),
           without_CAF_DJI_posthoc=compute([r for r in rows if r["iso"] not in ("CAF","DJI")]),
           interpretation="Descriptive, reference-dependent, noncausal, nonrepresentative; post-hoc influential-case sensitivity")
path=Path("research_outputs/AE-2026-001/c18_reference_sensitivity.json")
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,indent=2))

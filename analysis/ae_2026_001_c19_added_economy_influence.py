#!/usr/bin/env python3
"""AE C19: exact added-economy mean attribution and single-deletion influence.
Descriptive post-hoc sensitivity, not causal attribution, novelty, or an exclusion rule.
"""
import csv, hashlib, json, math, statistics
from pathlib import Path
SRC=Path("research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv")
EXPECTED="715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169"
if hashlib.sha256(SRC.read_bytes()).hexdigest()!=EXPECTED:
    raise SystemExit("FAIL CLOSED: source hash mismatch")
def positive(x):
    try:
        z=float(x)
        return math.isfinite(z) and z>0
    except (ValueError,TypeError): return False
with SRC.open(encoding="utf-8-sig",newline="") as f:
    source=list(csv.DictReader(f))
if len(source)!=217 or len({r["country_iso3"] for r in source})!=217:
    raise SystemExit("FAIL CLOSED: economy count or unique ISO mismatch")
B=[];A=[]
for r in source:
    p19=r["ag_value_added_per_worker_2019_constant2015usd"]
    p23=r["ag_value_added_per_worker_2023_constant2015usd"]
    if not (positive(p19) and positive(p23)): continue
    x={"iso":r["country_iso3"],"name":r["country_name"],"region":r["region"].strip(),
       "g":25*math.log(float(p23)/float(p19))}
    (B if positive(r["ag_value_added_per_worker_2000_constant2015usd"]) else A).append(x)
if (len(B),len(A))!=(153,16): raise SystemExit("FAIL CLOSED: cohort mismatch")
P=B+A
mu_b=statistics.mean(x["g"] for x in B)
mu_p=statistics.mean(x["g"] for x in P)
median_b=statistics.median(x["g"] for x in B)
median_p=statistics.median(x["g"] for x in P)
out=[]
for x in A:
    remain=[r["g"] for r in P if r["iso"]!=x["iso"]]
    out.append({"iso":x["iso"],"region":x["region"],"growth_log_pp_y":x["g"],
                "exact_gap_contribution":(x["g"]-mu_b)/len(P),
                "leave_one_out_mean":statistics.mean(remain),
                "leave_one_out_median":statistics.median(remain),
                "mean_drop_on_removal":mu_p-statistics.mean(remain)})
out.sort(key=lambda r:r["exact_gap_contribution"],reverse=True)
delta=mu_p-mu_b
if not math.isclose(sum(x["exact_gap_contribution"] for x in out),delta,abs_tol=1e-11):
    raise SystemExit("FAIL CLOSED: 16-case attribution identity failed")
two=sum(x["exact_gap_contribution"] for x in out if x["iso"] in ("CAF","DJI"))
if not math.isclose(two/delta,0.9772798785625784,abs_tol=1e-9):
    raise SystemExit("FAIL CLOSED: two-country influence changed")
result={"input_sha256":EXPECTED,"base_n":len(B),"added_n":len(A),"pooled_n":len(P),
        "base_mean":mu_b,"pooled_mean":mu_p,"gap":delta,
        "base_median":median_b,"pooled_median":median_p,
        "CAF_DJI_gap_share":two/delta,"added_economies":out,
        "interpretation":"Exact algebraic sample-mean contributions, not causal drivers. All deletions are post hoc; no observations are removed from primary analysis."}
dest=Path("research_outputs/AE-2026-001/c19_added_economy_influence.json")
dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps(result,indent=2,ensure_ascii=False))

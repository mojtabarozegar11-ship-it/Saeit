#!/usr/bin/env python3
"""Source-locked independent descriptive rank-stability audit of WDI vintage revisions.
Reads only the existing 155-economy real-data artifact; no new data or inference.
"""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

PAIRS = (("2024", "2025"), ("2025", "2026"), ("2024", "2026"))
EXPECTED_SIGN_FLIPS = {("2024", "2025"): 6, ("2025", "2026"): 6, ("2024", "2026"): 10}

def average_ranks(values):
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])
    out = [None] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        rank = (i + 1 + j) / 2
        for k in range(i, j):
            out[indexed[k][0]] = rank
        i = j
    return out

def pearson(x, y):
    a, b = statistics.mean(x), statistics.mean(y)
    numer = sum((i-a)*(j-b) for i,j in zip(x,y))
    den = math.sqrt(sum((i-a)**2 for i in x)*sum((j-b)**2 for j in y))
    if den == 0:
        raise ValueError("constant country ranks")
    return numer/den

def quantile(values, q):
    s = sorted(values)
    p = (len(s)-1)*q
    i = int(p)
    return s[i] + (s[min(i+1,len(s)-1)]-s[i])*(p-i)

def audit(data, sha):
    cohort = data["same_country_2000_2019"]
    rows = cohort["country_level_rates"]
    if cohort["cohort_n"] != 155 or len(rows) != 155 or len({r["iso3"] for r in rows}) != 155:
        raise ValueError("source fixed cohort must contain exactly 155 unique economies")
    if set(cohort["iso3"]) != {r["iso3"] for r in rows}:
        raise ValueError("cohort IDs differ from country-level observations")
    output = {}
    for a,b in PAIRS:
        x, y = [float(r[a]) for r in rows], [float(r[b]) for r in rows]
        if not all(math.isfinite(z) for z in x+y):
            raise ValueError("nonfinite source growth")
        diff = [v-u for u,v in zip(x,y)]
        abs_diff = [abs(d) for d in diff]
        flips = sum((u < 0 < v or v < 0 < u) for u,v in zip(x,y))
        if flips != EXPECTED_SIGN_FLIPS[(a,b)]:
            raise ValueError("independent sign-flip count does not reproduce original")
        top = sorted(({"iso3":r["iso3"], "annual_log_growth_revision_percentage_points":round(d*100,8)}
                      for r,d in zip(rows,diff)),key=lambda r:abs(r["annual_log_growth_revision_percentage_points"]),reverse=True)[:10]
        output[a+"_to_"+b] = {
            "n_fixed_economies":155,
            "spearman_rank_correlation":round(pearson(average_ranks(x),average_ranks(y)),9),
            "median_absolute_annual_log_growth_revision_percentage_points":round(statistics.median(abs_diff)*100,9),
            "p90_absolute_annual_log_growth_revision_percentage_points":round(quantile(abs_diff,0.9)*100,9),
            "economies_absolute_revision_over_1_percentage_point_per_year":sum(z>0.01 for z in abs_diff),
            "economies_absolute_revision_over_2_percentage_points_per_year":sum(z>0.02 for z in abs_diff),
            "sign_changes":flips,
            "top_absolute_revisions":top
        }
    return {"status":"REPRODUCED_DESCRIPTIVE_AUDIT; NO_CAUSAL_OR_NOVELTY_CLAIM",
            "source":data["source"],"source_json_sha256":sha,
            "country_panel_2026_sha256":data["country_panel_2026_sha256"],
            "fixed_cohort_n":155,"comparisons":output,
            "interpretation":"Rank and magnitude sensitivity to historical WDI release vintage, not a statistical test or causal effect."}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input_json")
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    raw=Path(args.input_json).read_bytes()
    data=json.loads(raw)
    report=audit(data,hashlib.sha256(raw).hexdigest())
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:{f:v for f,v in row.items() if f!="top_absolute_revisions"}
                      for k,row in report["comparisons"].items()},indent=2))

if __name__=="__main__":
    main()

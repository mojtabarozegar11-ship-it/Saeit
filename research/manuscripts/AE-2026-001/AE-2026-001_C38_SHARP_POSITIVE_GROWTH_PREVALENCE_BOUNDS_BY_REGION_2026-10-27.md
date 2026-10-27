# AE-2026-001 C38 — Sharp bounds on positive growth prevalence and regional heterogeneity

**27 October 2026. Internal AI secondary-data analysis; no human-author approval or journal submission.** This is a new descriptive sensitivity calculation, not a novel estimator, independent external validation, or a world-representative result.

## Source lock and estimand

Input: `research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv` on `research/mr-2026-001-novelty-audit`; Git blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`. Previously recorded SHA256: `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169` (not rehashed in this run). Series: WDI NV.AGR.EMPL.KD (constant 2015 USD per worker); endpoints 2000 and 2019, 2026-only fixed source snapshot. Unit is an equally weighted nonaggregate economy/territory record, not an agricultural worker. Valid growth requires positive finite values in both years, `g=100*ln(P2019/P2000)/19` log-percentage points/year. A missing endpoint means **unknown** growth, not zero.

For a group with N records, n observed growth rates, m=N-n missing rates, and k observed rates strictly exceeding a prespecified descriptive threshold t, the full-frame share with g>t is only partially identified:

`k/N <= Pr_frame(g>t) <= (k+m)/N`.

These bounds are **sharp** with unrestricted missing growth: assign all m below or all m above t. They are finite-frame deterministic bounds, not confidence intervals. Thresholds t=0,1,2,3,5 are exploratory post hoc reporting cutoffs, not statistical tests.

## Results — 217-record 2026-only frame

Observed endpoint pairs n=157; missing m=60; observed strictly positive growth k=132; observed nonpositive growth 25. The exact sharp fraction of the full frame with positive growth is **132/217 to 192/217 = 60.83% to 88.48%**. Thus a strict majority of the 217 records has positive growth under *any* assignment to the missing records, but its exact share is unidentified.

| Threshold g>t (annual log-pp) | Observed above t (of 157) | Sharp lower share (of 217) | Sharp upper share (of 217) | Majority guaranteed? |
|---|---:|---:|---:|---|
| 0 | 132 | 60.83% | 88.48% | Yes |
| 1 | 114 | 52.53% | 80.18% | Yes |
| 2 | 87 | 40.09% | 67.74% | No |
| 3 | 64 | 29.49% | 57.14% | No |
| 5 | 19 | 8.76% | 36.41% | No; even upper bound below 50% |

**Important distinction from C36:** C36 established sharp *median value* bounds. C38 establishes new *binary prevalence and threshold-classification* bounds and reveals region-level heterogeneity. It does not recalculate C36 as a new finding.

### Regional bounds for strictly positive growth (g>0)

| WDI region | N | Observed n | Positive k | Missing m | Sharp positive share interval | Positive majority guaranteed? |
|---|---:|---:|---:|---:|---|---|
| Latin America & Caribbean | 42 | 28 | 22 | 14 | 52.38%–85.71% | Yes |
| Middle East, North Africa, Afghanistan & Pakistan | 23 | 17 | 15 | 6 | 65.22%–91.30% | Yes |
| Sub-Saharan Africa | 48 | 37 | 30 | 11 | 62.50%–85.42% | Yes |
| Europe & Central Asia | 58 | 46 | 45 | 12 | 77.59%–98.28% | Yes |
| East Asia & Pacific | 37 | 22 | 14 | 15 | 37.84%–78.38% | **No** |
| South Asia | 6 | 6 | 5 | 0 | 83.33%–83.33% | Yes |
| North America | 3 | 1 | 1 | 2 | 33.33%–100.00% | **No** |
| **All** | **217** | **157** | **132** | **60** | **60.83%–88.48%** | **Yes** |

**Adversarial interpretation:** The overall positive-majority conclusion is robust for this finite frame, but it does **not** imply every region has a robust majority. East Asia & Pacific and North America can have either majority outcome depending on unobserved values. Regional bounds reflect WDI administrative metadata and mixed countries/territories; no population, worker or output weights are used. The South Asia result is based on only six records. No missingness mechanism, causal trend, global agricultural productivity growth or historical vintage stability is identified.

## Reproducible recipe (standard-library Python; not separately executed in this run)

```python
import csv, math
from collections import defaultdict
path="AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv"
regions=defaultdict(list)
with open(path, newline="", encoding="utf-8") as f:
    rows=list(csv.DictReader(f))
for r in rows:
    a=r["ag_value_added_per_worker_2000_constant2015usd"]
    b=r["ag_value_added_per_worker_2019_constant2015usd"]
    g=None
    if a and b:
        x,y=float(a),float(b)
        if math.isfinite(x) and math.isfinite(y) and x>0 and y>0:
            g=100*math.log(y/x)/19
    regions[r["region"].strip()].append(g)
assert len(rows)==217
observed=[g for vals in regions.values() for g in vals if g is not None]
assert len(observed)==157 and sum(g>0 for g in observed)==132
for t in [0,1,2,3,5]:
    k=sum(g>t for g in observed)
    print(t,k, k/217, (k+60)/217)
for region,vals in sorted(regions.items()):
    n=sum(g is not None for g in vals)
    k=sum(g is not None and g>0 for g in vals)
    N=len(vals)
    print(region,N,n,k,N-n,k/N,(k+N-n)/N,k>N/2)
```

## Release gate

This is a **post hoc** exploratory extension to the 2026-only sample and does not address the primary 155-economy 2024/2025/2026 vintage comparison. Historical ILOSTAT release files, direct countryatlas matched-vintage benchmark, independent denominator validation, author-led novelty evaluation and author approvals remain open. No fabricated data, DOI, experimental result, human authorship, manuscript ID, VPS use, payment, or live-site publication. **MAJOR REVISION / NO SUBMISSION.**

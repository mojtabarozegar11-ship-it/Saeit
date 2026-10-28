# AE-2026-001 C36 — Sharp finite-frame median bounds under unrestricted missing 2000–2019 growth

**27 October 2026 | New source-locked finite-sample partial-identification calculation | Internal AI analysis, not an original estimator, a world estimate, or journal approval.**

## Source and estimand
Input: `research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv` on branch `research/mr-2026-001-novelty-audit`, Git blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`. The previously recorded source SHA256 is `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169` (not rehashed in this run). The CSV has **N=217** nonaggregate economy/territory records; **n=157** have positive finite WDI `NV.AGR.EMPL.KD` in both 2000 and 2019; **m=60** do not. Compute `g_i=100*ln(P2019/P2000)/19` annual log-percentage points for the 157 observed pairs. This is the **2026-only 157-economy frame**, not the primary 155-economy historical-vintage panel or the 153-economy three-endpoint panel.

## Sharp nonparametric finite-frame median interval
Let `g_(j)` denote the j-th ascending observed growth rate (one-indexed). The hypothetical median of the **217** frame records is the **109th** ascending rate. With **60 unrestricted missing** growth rates, its exact sharp lower and upper bounds are

`[g_(109-60), g_(109)] = [g_(49), g_(109)] = [1.423959, 3.689876]` log-percentage points/year.

| Quantity | Rank / count | Observed rate | Country code at boundary |
| --- | ---: | ---: | --- |
| Lower attainable full-frame median | 49th of 157 observed | **1.423959** | LBR |
| Median of 157 observed pairs | 79th of 157 observed | **2.355575** | BGR |
| Upper attainable full-frame median | 109th of 157 observed | **3.689876** | SWE |
| Positive observed growth | 132 of 157 | not a growth rate | — |
| Nonpositive observed growth | 25 of 157 | not a growth rate | — |

**Proof of sharpness:** assigning all 60 missing rates strictly below every observed rate makes the 109th full-frame order statistic equal to the 49th observed; assigning them all strictly above makes it the 109th observed. For any intermediate assignment the full-frame 109th order statistic cannot be below `g_(49)` or above `g_(109)`. Both extremes are mathematically attainable because the missing rates are unrestricted. This is deterministic finite-frame partial identification, **not** a sampling confidence interval or an imputation model.

**New qualified finding:** the full-frame *equal-economy* median would be **positive for every assignment of finite missing growth rates**, because even its sharp lower bound is 1.423959>0. Equivalently, 132 already-observed positive rates exceed half of the 217 records (109). **The exact full-frame median remains unidentified** within the interval; neither its value nor the missingness mechanism is estimated. This is not a claim that the world's population-, worker- or production-weighted agricultural productivity grew.

## Distinguish from prior C34 mean tipping point
C34 already established that the 217-frame **mean** is unidentified and would change sign only if the 60 unknown rates averaged below -6.276071 log-pp/year. **Do not count that older mean tipping point as a new result here.** C36 instead derives a **new sharp median interval** and its positive-sign robustness without any distributional assumption on missing values. The interval's width is 2.265916 log-pp/year and should not be mistaken for a precision estimate.

## Reproducible standard-library Python recipe
```python
import csv, math
with open("AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv", newline="", encoding="utf-8") as fh:
    records = list(csv.DictReader(fh))
g = []
for row in records:
    a = row["ag_value_added_per_worker_2000_constant2015usd"]
    b = row["ag_value_added_per_worker_2019_constant2015usd"]
    if a and b and math.isfinite(float(a)) and math.isfinite(float(b)) and float(a)>0 and float(b)>0:
        g.append((100*math.log(float(b)/float(a))/19, row["country_iso3"]))
g.sort()
N, n = len(records), len(g)
k = (N+1)//2
assert (N, n, N-n, k) == (217, 157, 60, 109)
assert sum(v>0 for v, _ in g) == 132
assert g[k-(N-n)-1][1] == "LBR" and g[k-1][1] == "SWE"
print("sharp median interval:", g[k-(N-n)-1], g[k-1])
```

## Adversarial scientific interpretation and release gate
- The 217-record frame mixes countries and territories and weights each record equally; it is **not** a census of agricultural workers or a globally representative panel.
- The 60 missing growth rates are hypothetical counterfactual quantities; no zero is assigned, and missing values are not treated as real observed growth.
- The bounds are a standard order-statistic result applied to this dataset, **not a novel statistical method**, a preregistered analysis, causal evidence or independent external validation.
- The positive sign is robust **only for the defined 217-record finite frame, 2000–2019 horizon, 2026 snapshot and log-growth definition**. It says nothing about 2019–2023, the 155-country three-vintage panel, or future WDI releases.
- Historical ILOSTAT 2024/2025, shared-source dependence, matched direct `countryatlas` benchmark, full novelty comparison and human-author approvals remain unresolved.

**AI-only decision: MAJOR REVISION / NO SUBMISSION.** No author signature, journal action, external reviewer, manuscript ID, data fabrication, VPS use, payment or live-site change.

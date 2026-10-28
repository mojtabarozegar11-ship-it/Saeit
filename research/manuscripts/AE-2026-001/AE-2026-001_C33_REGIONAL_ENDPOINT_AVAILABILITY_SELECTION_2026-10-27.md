# AE-2026-001 C33 — regional endpoint-availability selection audit (2026-only WDI snapshot)

**27 October 2026. Original finite-sample re-tabulation of a previously source-locked 217-economy CSV.** This is an internal descriptive data audit, **not** a new WDI vintage, global estimate, statistical significance test, causal mechanism, or publication novelty.

## Data provenance and reproducible rule

- Input: [AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv](AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv), Git blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`, source-file SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169` as recorded in the manuscript provenance. The snapshot's official WDI source-update label was 8 October 2026; the CSV was deposited 25 October 2026.
- Indicator: `NV.AGR.EMPL.KD`, agriculture, forestry and fishing value added per worker (constant 2015 US dollars); official definition and data-license metadata: https://databank.worldbank.org/metadataglossary/world-development-indicators/series/NV.AGR.EMPL.KD (World Bank/ILOSTAT source; CC BY 4.0).
- Read the CSV with proper quoted-field handling. Strip whitespace from `region` (several region strings contain trailing spaces). Define each year's availability as **finite and strictly positive** numeric value; blank is missing, not zero. Concatenate flags in chronological order 2000/2019/2023 to form `000`, `011`, `100`, `110` or `111`. No imputation or weighting.
- The region assignments are **exactly the metadata categories in this snapshot**, including the long `Middle East, North Africa, Afghanistan & Pakistan` label. They are not a new geographic taxonomy or country-population weights.

## New regional census (directly calculated from the committed CSV)

| WDI metadata region | All economy records | Complete 2000/2019/2023 (111) | 2019/2023 pair (011+111) | No endpoints (000) | 2019/2023 only (011) | 2000/2019 only (110) | 2000 only (100) | Complete / all |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Latin America & Caribbean | 42 | 28 | 28 | 14 | 0 | 0 | 0 | 66.67% |
| Middle East, North Africa, Afghanistan & Pakistan | 23 | 15 | 20 | 0 | 5 | 2 | 1 | 65.22% |
| Sub-Saharan Africa | 48 | 36 | 43 | 4 | 7 | 1 | 0 | 75.00% |
| Europe & Central Asia | 58 | 45 | 47 | 10 | 2 | 1 | 0 | 77.59% |
| East Asia & Pacific | 37 | 22 | 24 | 13 | 2 | 0 | 0 | 59.46% |
| South Asia | 6 | 6 | 6 | 0 | 0 | 0 | 0 | 100.00% |
| North America | 3 | 1 | 1 | 2 | 0 | 0 | 0 | 33.33% |
| **Total** | **217** | **153** | **169** | **43** | **16** | **4** | **1** | **70.51%** |

**Integrity checks:** 43+16+1+4+153=217; 153+16=169 valid 2019/2023 pairs; 153+4=157 valid 2000/2019 pairs; 153+4+1=158 positive 2000 observations; 153+16+4=173 positive 2019 observations. These agree with earlier C13/C14 aggregate counts; the **regional cross-tabulation and explicit regional coverage denominators** are the additional C33 result. The 155-economy *historical three-vintage* fixed cohort is separate and must never be relabeled as these 153 cases.

## Particularly important coverage qualifications

- The 16 economies with a valid 2019/2023 pair but no valid 2000 value are concentrated in four metadata regions: Sub-Saharan Africa **7**, Middle East/North Africa/Afghanistan/Pakistan **5**, Europe/Central Asia **2**, East Asia/Pacific **2**. None belong to the other three regions in this source file.
- Of the 43 records missing all three endpoints, Latin America/Caribbean contributes **14** and East Asia/Pacific **13**; this may reflect source coverage and territory composition, not zero agricultural production.
- **North America is 1/3 complete in this file**: Canada is `111`; Bermuda and the United States are `000`. This is a statement about **this indicator's committed three-year extract**, not a claim that the United States has no agriculture, no productivity statistics, or is absent from WDI in general. Verify directly against the dated source API before any prominent country-specific assertion in a public manuscript.
- South Asia's 6/6 coverage reflects the **six records assigned to that WDI metadata region in this CSV**; it is not a population-weighted South Asian coverage rate.
- The regional spread (33.33% to 100%) and missingness patterns show that complete-case inclusion differs by region in the *observed file*. This **does not establish** a missing-at-random or missing-not-at-random statistical mechanism, nor justify extrapolating unweighted 153-country medians to global agricultural output.

## Replication recipe (Python standard library)

```python
import csv, collections, math
from pathlib import Path
p = Path("research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv")
rows = list(csv.DictReader(p.open(encoding="utf-8", newline="")))
assert len(rows) == 217
counts = collections.defaultdict(collections.Counter)
for r in rows:
    region = r["region"].strip()
    flags = []
    for y in (2000, 2019, 2023):
        raw = r[f"ag_value_added_per_worker_{y}_constant2015usd"]
        value = float(raw) if raw else math.nan
        flags.append("1" if math.isfinite(value) and value > 0 else "0")
    counts[region]["".join(flags)] += 1
assert sum(sum(c.values()) for c in counts.values()) == 217
assert sum(c["111"] for c in counts.values()) == 153
assert sum(c["011"] for c in counts.values()) == 16
for region, c in sorted(counts.items()):
    n = sum(c.values())
    print(region, n, c["111"], c["111"] + c["011"], c["000"], c["011"], c["110"], c["100"], round(100*c["111"]/n, 2))
```

## Internal AI adversarial review and release gate

This is a **descriptive availability census**, not independent new data, peer review or proof of the AE manuscript's novelty. Region categories are heterogeneous and small in North America and South Asia; no standard errors or hypothesis tests are warranted from this selected administrative panel. The 2026-only 153/169/217 cohorts must remain distinct from the 155-economy historical-vintage cohort. **Do not** use these coverage figures to claim global representativeness or to impute missing values. C33 does not resolve historical ILOSTAT 2024/2025 provenance, exact three-vintage `countryatlas` numerical comparison, shared-source independence, or final author declarations. **MAJOR REVISION / NO SUBMISSION.**

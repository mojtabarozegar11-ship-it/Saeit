# AE-2026-001 C13 — Exact identity of four 2023-attrited economies and why the 2000–2019 median stayed unchanged

**Date:** 2026-10-26. **Type:** new country-level secondary calculation from the previously committed official 2026 WDI snapshot; **no new API download, historical vintage, employment data or causal inference**.

## Source and algorithm
Source file: [AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv](AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv), GitHub blob SHA `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`, 217 nonaggregate economy rows. Parse quoted CSV fields, keep strictly positive finite 2000 and 2019 agricultural value-added-per-worker observations, and compute `100*ln(y2019/y2000)/19` in annual log-percentage points. Define the 2023 balanced subset by also requiring a positive finite 2023 observation. Rank the original 157 2000–2019 growth rates ascending. This was recomputed independently from the **full source CSV bytes fetched from the target GitHub branch**, not copied from an existing manuscript summary.

## Newly resolved attrition identities
| Country code | Country/economy | WDI region | 2000–2019 growth (log-pp/year) | Ascending rank among 157 |
|---|---|---|---:|---:|
| SDN | Sudan | Sub-Saharan Africa | 0.023310 | 27 |
| SYR | Syrian Arab Republic | MENA/Afghanistan/Pakistan | 0.074789 | 28 |
| PSE | West Bank and Gaza | MENA/Afghanistan/Pakistan | 4.110956 | 118 |
| UKR | Ukraine | Europe/Central Asia | 4.838383 | 136 |

These **four economies have valid 2000/2019 endpoints but lack a positive 2023 observation in this particular archived API extract**. This is not evidence that their 2023 productivity was zero, nor an assertion about real-world causes of missingness.

## Exact aggregate reconciliation
- 2000–2019 positive pairs: **157**; positive three-endpoint balanced cases: **153**; attrition **4** (two observations below and two above the median).
- Original 157-economy median = **2.3555752946417114 log-pp/year**, 79th ordered value, **BGR** (Bulgaria).
- Balanced 153-economy median = **2.3555752946417114 log-pp/year**, 77th ordered value, **the same BGR observation**.
- Original mean = **2.3984983654433942 log-pp/year**; balanced mean = **2.402070624051143 log-pp/year**; mean change on balancing = **+0.0035722586077488 log-pp/year**.
- The median remains unchanged **because two deleted observations lie on each side of its rank**, not because the four excluded economies have identical trajectories or because missingness is ignorable.

## Implication and limitations
The unchanged 2000–2019 median in manuscript §3.2 is an **order-statistic cancellation** in this snapshot. Do not claim a general robustness result for other endpoints, indicators or vintages. The 157-economy current-source panel is not the 155-economy three-vintage historical cohort. No employment denominator, countryatlas numerical benchmark or journal-level novelty is established. **MAJOR REVISION / NO SUBMISSION**.

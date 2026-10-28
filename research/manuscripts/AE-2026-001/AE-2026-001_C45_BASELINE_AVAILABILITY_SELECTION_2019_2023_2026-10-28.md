# AE-2026-001 C45 — Baseline-availability selection in the 2019–2023 growth comparison

**Date:** 2026-10-28. **Stage:** internal scientific revision, **NOT SUBMITTED**.

## Source and estimand
Official World Bank WDI NV.AGR.EMPL.KD 2026 snapshot, 217 economy/territory records, source Git blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`. World Bank indicator metadata: https://data.worldbank.org/indicator/NV.AGR.EMPL.KD . The annualized log growth rate is `100 * ln(value_2023 / value_2019) / 4` in log percentage points per year, with positive finite endpoint requirements. The comparison is **not** a 2024/2025/2026 vintage comparison and does not identify a causal selection mechanism.

## Independently reproduced group statistics and new 169-versus-153 cohort comparison

| 2019–2023 observed subset | N | Median annual log growth (pp) | Mean (pp) | Positive / negative | Median 2019 indicator (constant 2015 US$) |
|---|---:|---:|---:|---:|---:|
| All eligible 2019 and 2023 observations | **169** | **0.9751104652** | **0.8101423204** | **101 / 68** | not used for this contrast |
| With positive 2000 baseline (111 mask) | **153** | **0.8904395335** | **0.5417354215** | **90 / 63** | **6237.9188112** |
| Without positive 2000 baseline (011 mask) | **16** | **2.6731880547** | **3.3767832913** | **11 / 5** | **2840.9653854** |

The full-169 median minus the balanced-153 median is **+0.0846709317 log-pp/year**. The 16 late-baseline cases have a larger observed median growth than the 153 complete-baseline cases, but that is a descriptive association within the 2026 snapshot, **not evidence that missingness caused growth**.

**Sixteen 011 cases (ISO3):** AFG, AGO, BHR, CAF, CIV, DJI, GEO, GHA, GNQ, KWT, LBY, PNG, SLB, STP, TCD, TKM.

| WDI region | 011 cases | 111 cases |
|---|---:|---:|
| Middle East, North Africa, Afghanistan & Pakistan | 5 | 15 |
| Sub-Saharan Africa | 7 | 36 |
| Europe & Central Asia | 2 | 45 |
| East Asia & Pacific | 2 | 22 |
| Latin America & Caribbean | 0 | 28 |
| South Asia | 0 | 6 |
| North America | 0 | 1 |

## Scientific interpretation and falsification boundary
- Selecting the three-endpoint 153-economy panel changes the descriptive 2019–2023 estimand relative to the 169-economy two-endpoint panel. Do not silently treat their medians as the same statistic.
- The small **0.08467** median difference does not prove missing-at-random or that selection is ignorable in other years, regions or releases.
- The **16** late-baseline cases are not an experimental comparison group; level and growth differences may reflect confounding, measurement changes or country composition.
- The 2026 WDI per-worker indicator is composite and cites ILOSTAT; this audit is not independent employment validation.
- Existing C13/C14 availability masks **and C30/C31 signed-growth group medians and 2019 level medians** are reused as context, **not counted as new discoveries**. The incremental C45 result is specifically the **full 169-economy signed median (0.9751104652), full-frame mean and sign counts, and its exact +0.0846709317 median contrast against the 153-economy panel**. It does not claim discovery of the 16-versus-153 difference, which C31 already discussed.
- Neither an original estimator nor journal-ready novelty is claimed.

**Reproduction:** `python research/manuscripts/AE-2026-001/analysis/c45_2019_2023_baseline_selection_diagnostic.py`. The program checks 217 unique source ISO3 codes and exact 169/153/16 eligibility counts, then prints the group results. This document was independently calculated from the full GitHub CSV; a CI execution of the new Python file must be checked separately before asserting that the Python implementation itself ran.

**Author decision gate:** MAJOR REVISION / NO SUBMISSION. Human author review, historical ILOSTAT provenance, direct countryatlas three-vintage benchmark and final publication disclosures remain outstanding.

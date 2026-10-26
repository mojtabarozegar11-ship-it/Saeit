# AE-2026-001 C14 — Exact three-endpoint availability-mask census in the dated 2026 WDI country panel

**Date:** 2026-10-26. **Source:** committed official WDI country panel [CSV](AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv), GitHub blob SHA `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`, **217** nonaggregate economies. **Analysis:** direct independent row-wise positive-finite observation mask; no imputation, no new download, no causal missingness explanation.

## Exact availability-pattern table

Define a 3-bit mask in **2000 / 2019 / 2023** order; 1 = positive finite observed `NV.AGR.EMPL.KD` value, 0 = absent or nonpositive (no zero imputation).

| Mask | 2000 | 2019 | 2023 | Economies | Interpretation |
|---|---|---|---|---:|---|
| 000 | no | no | no | **43** | no eligible endpoint |
| 001 | no | no | yes | **0** | none |
| 010 | no | yes | no | **0** | none |
| 011 | no | yes | yes | **16** | no eligible 2000 baseline |
| 100 | yes | no | no | **1** | **YEM (Yemen)** |
| 101 | yes | no | yes | **0** | none |
| 110 | yes | yes | no | **4** | **PSE, SDN, SYR, UKR** (see C13) |
| 111 | yes | yes | yes | **153** | fully balanced three-endpoint cohort |
| **Total** | | | | **217** | exhaustive mutually exclusive masks |

## Internal marginal reconciliation
- Positive observations: 2000 **158 = 1+4+153**; 2019 **173 = 16+4+153**; 2023 **169 = 16+153**.
- Positive endpoint pairs: 2000–2019 **157 = 4+153**; 2000–2023 **153**; 2019–2023 **169 = 16+153**.
- The **2023-positive set is a strict subset of the 2019-positive set** for this *particular* three-date extract (169/173). This is a descriptive inclusion relation **in the observed availability masks**, not a law of WDI coverage across time or historical releases.
- All 16 cases lacking 2000 but observed in 2019 and 2023 have no computable 2000-based growth. Their 2019–2023 growth could be computed as a separate **169-economy, differently selected estimand**; it must not be compared as if it used the original 153 balanced economies.
- The four 110 cases and their 2000–2019 rank positions are audited separately in C13. The 000/011/100 masks were **not** evidence of zero agricultural output, employment, or productivity.

## Reproducibility
From the source CSV, apply `isfinite(float(value)) and float(value)>0` to each of the three columns, with blank cells classified absent; group by the resulting 3-bit string and count. The eight exhaustive counts sum to 217 and reproduce all previously reported marginals. The computation was executed directly on the full GitHub-fetched CSV; the existing 155-economy **historical-vintage** fixed cohort is a distinct sample.

**Decision:** improves transparent denominator accounting but neither establishes novelty over countryatlas nor provides archived ILOSTAT employment, independent worker measurement, a causal missingness model, or a journal-ready original research result. **MAJOR REVISION / NO SUBMISSION**.

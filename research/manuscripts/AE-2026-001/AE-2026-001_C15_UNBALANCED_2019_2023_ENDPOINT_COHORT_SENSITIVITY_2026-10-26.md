# AE-2026-001 C15 — Source-locked 2019–2023 unbalanced-cohort influence and outlier sensitivity

**Date:** 26 October 2026. **Data:** original official World Bank WDI country panel, indicator `NV.AGR.EMPL.KD` (constant-2015-USD agricultural value added per worker), 217 nonaggregate economies, `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`. Source SHA256 from independent GitHub runner: `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`; GitHub blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`.

**New actual computation:** [GitHub Actions run 40352237660](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40352237660) **COMPLETED / SUCCESS**, [artifact 12663744039](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40352237660/artifacts/12663744039). Executable, fail-closed standard-library program: `analysis/wdi_2019_2023_unbalanced_cohort_sensitivity.py`; workflow: `.github/workflows/ae-2026-001-2019-2023-cohort-influence.yml`. It requires the exact six CSV columns, positive finite endpoints and unique ISO3s; checks 217 / 153 / 16 counts, produces a country-level JSON and retains it as an artifact. No imputation or external data was used.

## Estimand and cohort decomposition

For each country with positive 2019 and 2023 endpoints, `g_i = 100 × ln(P_i,2023 / P_i,2019) / 4` in **annual log-percentage points**. The 153 economies with 2000/2019/2023 endpoints are a **balanced cohort**; another 16 have 2019/2023 but lack positive 2000. The 169-economy 2019–2023 cross-section is a **different estimand** from the 153-country panel and from the fixed 155-country historical-vintage panel.

| Cohort / sensitivity | Economies | Median annual log-pp | Mean annual log-pp | Positive / negative |
|---|---:|---:|---:|---:|
| Balanced 2000/2019/2023 | **153** | **0.890440** | **0.541735** | 90 / 63 |
| Additional 2019/2023 only | **16** | **2.673188** | **3.376783** | 11 / 5 |
| All 2019/2023 eligible | **169** | **0.975110** | **0.810142** | 101 / 68 |
| All eligible except CAF and DJI (post hoc only) | **167** | **0.890440** | **0.547907** | Not interpreted as a pre-specified sample |

- Adding the 16 otherwise excluded economies shifts the **median by +0.084671 log-pp/year** and the **mean by +0.268407 log-pp/year** compared with the balanced 153. These are **differences of sample summaries**, not paired within-country growth changes.
- The 16 additional countries are **AFG, AGO, BHR, CAF, CIV, DJI, GEO, GHA, GNQ, KWT, LBY, PNG, SLB, STP, TCD, TKM**. Their region counts in the source metadata are Sub-Saharan Africa **7**, Middle East/North Africa/Afghanistan/Pakistan **5**, Europe/Central Asia **2**, East Asia/Pacific **2**.
- Two influential positive values in the added cohort are **CAF +28.1538** and **DJI +17.2598** log-pp/year (2019–2023). Removing *only those two* after seeing the data changes the 167-economy mean to **0.547907** and its difference from the balanced mean to **+0.006171**. This is a transparent **post-hoc influence check**, **not** evidence that those observations are erroneous or should be discarded.
- The observed mask census from C14 still holds: 000=43, 011=16, 100=1, 110=4, 111=153, other masks=0.

## Scientific interpretation and restrictions

This quantifies **composition and high-leverage sensitivity** for the 2019–2023 endpoint comparison; it does **not** change the previously reproduced paired 153-country early/late growth analysis in manuscript §§3.6–3.7. No COVID-19, policy, conflict, environmental, or WDI revision cause is identified. Country-equal-weighted summaries are **not** world aggregates; endpoints are subject to revisions and the four-year horizon is short. The comparison is **not** a historical 2024/2025 ILOSTAT vintage reconstruction, independent worker count, countryatlas head-to-head benchmark, or a novel estimator.

**Decision:** add this explicitly as an additional cohort-sensitivity subsection, preserving the 153/155/157/169 denominator distinctions. **MAJOR REVISION / NO SUBMISSION**; no author attestation, journal approval or Manuscript ID.

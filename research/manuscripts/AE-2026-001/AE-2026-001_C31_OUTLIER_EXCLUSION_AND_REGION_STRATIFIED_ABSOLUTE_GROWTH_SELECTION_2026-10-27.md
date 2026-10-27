# AE-2026-001 C31 — Extreme-economy exclusion and within-region rank robustness of baseline-missing growth dispersion

**27 October 2026.** New deterministic, country-level secondary calculations from the committed **2026-only** WDI observed-country panel. This is an internal descriptive robustness audit, **not** an independent data vintage, population estimate, causal inference, journal novelty, or proof of an ILOSTAT revision mechanism.

## Original, source-locked input
- [Official WDI 2026 observed-country panel](AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv), GitHub blob SHA `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`; original source SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`.
- Series: `NV.AGR.EMPL.KD`, constant 2015 US$ per worker, 2019 and 2023. Filter to strictly positive finite endpoints: **169 economies**. Split by positive finite 2000 baseline: **153 present (mask 111)** and **16 missing (mask 011)**. The exhaustive 217-economy masks are documented in [C14](AE-2026-001_C14_THREE_ENDPOINT_AVAILABILITY_MASK_CENSUS_2026-10-26.md); C13 identifies the four distinct 110 economies.
- Compute `g_i = 100*ln(P_i,2023/P_i,2019)/4` annual log-percentage points. The comparison concerns **absolute** `|g_i|` as a *four-year endpoint-change magnitude*, **not** annual time-series volatility or variance estimated from repeated annual observations. Calling it 'volatility' is shorthand only and should be avoided in final manuscript claims.

## New question A — Is the C30 absolute-growth contrast entirely driven by CAF and DJI?

| Descriptive statistic | 153 baseline-present | 16 baseline-missing | 14 baseline-missing excluding CAF and DJI |
|---|---:|---:|---:|
| Median absolute annual log growth, log-pp/year | **2.316370** | **4.759665** | **4.498140** |
| Mean absolute annual log growth, log-pp/year | 3.772972 | 6.406042 | **4.077360** |
| Median **signed** annual log growth, log-pp/year | +0.890440 | +2.673188 | **+0.808881** |
| Count with absolute growth >5 log-pp/year | 40/153 | 7/16 | **5/14** |
| Count with absolute growth >10 log-pp/year | 9/153 | 2/16 | **0/14** |

- Removed cases: **CAF +28.153795** and **DJI +17.259840** log-pp/year. Both are in the 16-economy missing-baseline group. Exclusion is an explicitly post hoc *influence sensitivity*, not a justified data-cleaning rule; they remain in the primary analysis.
- The missing-baseline group's median absolute four-year endpoint growth remains higher than the 153-economy group's after both exclusions (4.498140 vs 2.316370). In contrast, the missing-baseline **signed** median changes from +2.673188 to +0.808881, now below +0.890440. Thus the signed-growth headline is highly sensitive to two extreme economies, while the absolute-growth median contrast is less so. This is descriptive, not causal.

## New question B — Do country-pair rank comparisons survive exclusion and geographic restriction?

Define the finite-sample pairwise statistic as the fraction of all cross-group country pairs for which `|g_missing| > |g_present|`. No ties occurred in the calculations.

| Comparison | Baseline-missing country higher absolute growth / all eligible pairs | Fraction |
|---|---:|---:|
| All 16 versus all 153, pooled | **1,597/2,448** | **0.652369** |
| Excluding CAF and DJI: 14 versus 153, pooled | **1,293/2,142** | **0.603641** |
| Within-region pairs only, all 16 | **291/461** | **0.631236** |
| Within-region pairs only, excluding CAF and DJI | **241/410** | **0.587805** |

**Region-specific cross-group comparisons of absolute growth:**

| Region | All baseline-missing cases | After removing CAF and DJI |
|---|---:|---:|
| Middle East, North Africa, Afghanistan & Pakistan | 63/75 = 0.840000 | 49/60 = 0.816667 |
| Sub-Saharan Africa | 132/252 = 0.523810 | **96/216 = 0.444444** |
| Europe & Central Asia | 63/90 = 0.700000 | 63/90 = 0.700000 |
| East Asia & Pacific | 33/44 = 0.750000 | 33/44 = 0.750000 |

The **Sub-Saharan Africa direction reverses after removing CAF**: 96/216 of within-region pairs have a higher absolute growth in the baseline-missing group. The global pooled fraction remains above 0.5 after exclusions, but regional patterns are heterogeneous and the 16-country group is small. Neither these proportions nor the pooled region-matched ratio are population probabilities; regional comparisons are not balanced by country or region size.

## Reproduction algorithm and integrity controls

1. Parse the quoted six-column CSV from the exact GitHub branch and confirm 217 unique nonaggregate ISO3 rows.
2. Filter rows with finite positive 2019 and 2023 `NV.AGR.EMPL.KD`; confirm n=169 and the C14 153/16 split by 2000 validity.
3. Calculate each country's `g_i=100*log(P2023/P2019)/4` and `abs(g_i)`. Use exact sorted median (average of two middle values for even n), arithmetic mean and strict threshold comparisons.
4. Exclude only `country_iso3 in {CAF,DJI}` **from the 16-case group for the sensitivity**. Do not alter the primary 153/16 panel or the 155-economy historical-vintage cohort.
5. Enumerate all 16×153=2448 and 14×153=2142 cross-group pairs, count strict `abs(g_missing)>abs(g_present)`. Repeat only within pairs with exactly matching trimmed `region` values: 461 and 410 pairs respectively. There were no ties.
6. No missing-value imputation, bootstrap, significance test, sampling design, ILO historical archive acquisition or inferential claim was performed.

## Internal critical AI review and author release gate

- **Pass (arithmetic and sample identities):** Counts, denominators, outlier exclusions, within-region pairs and strict rankings are independently recomputable from the locked source panel.
- **Major interpretation correction:** With only two endpoints, `|g_i|` is the magnitude of annualized four-year **net growth**, not within-period volatility. The previous C30 title and informal 'growth-volatility distribution' wording could mislead; final manuscript must prefer **absolute endpoint growth magnitude**.
- **Major limitations:** The 16-country group is selected by 2000 missingness; regions have very unequal sample sizes. Removing CAF/DJI is post hoc and not evidence those observations are erroneous. Ranking results do not explain missingness, prove source independence, establish historical WDI revision causation, or constitute a new statistical estimator.
- **Release gate:** Historical ILOSTAT 2024/2025 provenance and actual three-vintage `countryatlas::compare_vintages` remain open. Human author must approve the final scientific text and declarations before any journal action. **MAJOR REVISION / NO SUBMISSION.**

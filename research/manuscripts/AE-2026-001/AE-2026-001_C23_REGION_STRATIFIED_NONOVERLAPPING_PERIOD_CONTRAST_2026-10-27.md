# AE-2026-001 C23 — Region-stratified within-economy non-overlapping-period growth contrast

**2026-10-27 | Newly calculated secondary diagnostic on the previously locked 2026 WDI country panel; not a new vintage, causal analysis, or journal novelty claim.**

## Source, estimand and cohort
Input: `research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`; GitHub blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`, previously verified raw SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`. The same **153** nonaggregate economies have positive, finite productivity at **2000, 2019 and 2023**. No zero imputation, new observations, region weights, sampling weights or historical releases were used.

For each economy i: `g_early=100*ln(P_2019/P_2000)/19`, `g_late=100*ln(P_2023/P_2019)/4`, and **`d_i=g_late-g_early`** in log-percentage points/year. This is a **contrast of non-overlapping time intervals** and is *not* the prior C13/C14 availability-mask calculation, the C5 2000–2019 versus 2000–2023 overlapping-horizon contrast, or the 155-economy cross-vintage cohort.

## New regional audit (source CSV recomputed row by row)

| Region (WDI dated metadata) | n | Median paired d (log-pp/y) | Mean paired d | Slower (d<0) | Faster (d>0) | Median d excluding this region |
|---|---:|---:|---:|---:|---:|---:|
| East Asia & Pacific | 22 | -1.070216 | +0.544724 | 14 | 8 | -2.075186 |
| Europe & Central Asia | 45 | -2.925058 | -3.069024 | 36 | 9 | -1.505431 |
| Latin America & Caribbean | 28 | -0.764303 | -1.540432 | 19 | 9 | -2.249001 |
| Middle East, North Africa, Afghanistan & Pakistan | 15 | -0.785653 | -2.845567 | 9 | 6 | -2.065277 |
| North America | 1 | +0.959860 | +0.959860 | 0 | 1 | -1.942261 |
| South Asia | 6 | -3.821188 | -1.674339 | 4 | 2 | -1.924950 |
| Sub-Saharan Africa | 36 | -2.368818 | -1.766872 | 27 | 9 | -1.895728 |
| **All regions** | **153** | **-1.925832** | **-1.860335** | **109** | **44** | — |

Across the same 153 economies, the median early growth is **+2.355575** log-pp/year, the median late growth is **+0.890440** log-pp/year; their difference **-1.465136** is **not** the median paired difference **-1.925832**. Exactly **49** economies switched from positive early growth to negative late growth, **11** switched negative to positive, **79** remained positive and **14** remained negative. These four mutually exclusive categories sum to **153**.

**New sensitivity finding:** after excluding each WDI region in turn, the pooled paired median remains negative, ranging **-2.249001 to -1.505431** log-pp/year. This does not establish representative global deceleration; the North America stratum contains only one eligible economy, and a 4-year window is more sensitive to transient events than a 19-year window.

## Reproduction recipe
Read the cited exact CSV; parse quoted country fields; select strictly positive finite values at all three endpoints; calculate natural-log rates with denominators 19 and 4; group by the literal trimmed WDI region string; compute medians and means of `d`, sign counts and leave-one-region-out medians. **Do not use the 155-economy historical-vintage cohort**. Report the seven group sizes summing to 153 and 109+44=153. Calculations were executed in the connected GitHub tool session from the fetched full CSV; **no dedicated CI run or artifact is claimed**.

## Interpretation and editorial decision
This adds a *regional robustness check* to an already known paired period contrast; it does not identify structural breaks, causal drivers, revision mechanisms, independent ILO employment, national representativeness, historical ILOSTAT 2024/2025 archives or novel estimators. No country was excluded from the main analysis. Any journal-facing claim requires explicit source-date labeling, separate reporting of 4-year and 19-year estimands, and review of prior work. **MAJOR REVISION / NO SUBMISSION.**

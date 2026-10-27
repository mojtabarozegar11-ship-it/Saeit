# AE-2026-001 C28 — Baseline-productivity quartile heterogeneity in the 2026-only period contrast

**Date:** 27 October 2026. **Status:** original secondary, exploratory calculation from the already committed official 2026 WDI panel; not a new dataset, historical-vintage finding, structural-break test or causal effect.

## Source and independent analytical question
The locked CSV `research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`, GitHub blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`, contains 217 nonaggregate economies. Exactly 153 have strictly positive finite agricultural value added per worker (constant 2015 USD) at 2000, 2019 and 2023. This is **not** the primary 155-economy 2024/2025/2026 fixed-vintage cohort.

Question: is the descriptive slowdown between the 2000–2019 and 2019–2023 nonoverlapping windows uniform across **baseline year-2000 agricultural productivity** levels? This adds a baseline-stratified heterogeneity diagnostic to C23/C25 rather than repeating their regional or resampling analyses.

## Reproducible method
For each of the 153 economies calculate `E=100*ln(P2019/P2000)/19`, `L=100*ln(P2023/P2019)/4`, `d=L-E`. Sort the 153 observations by positive `P2000` ascending; assign zero-based sorted row index `i` to quartile `1+floor(4*i/153)` (39,38,38,38 economies). No weighting, country exclusions beyond positive complete cases, imputation, post hoc regrouping, or claims of random sampling. Compute medians of d, E and L within each quartile; count d<0. Compute ordinary Spearman rank correlation between log(P2000) and d over all 153 cases; log is monotonic so the rank is unchanged.

## New numerical findings

| Year-2000 productivity quartile | n | Baseline P2000 range (constant 2015 USD/worker) | Median paired d (log-pp/y) | Mean paired d | d<0 | Median E | Median L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Q1, lowest | 39 | 236.876–1,482.791 | −2.650990 | −2.198803 | 31 | +2.436783 | −0.197479 |
| Q2 | 38 | 1,492.444–3,931.747 | −2.493042 | −2.046176 | 29 | +2.773977 | +1.105895 |
| Q3 | 38 | 4,056.653–12,732.239 | −0.460747 | −1.312502 | 24 | +2.376875 | +2.261046 |
| Q4, highest | 38 | 12,891.751–82,265.571 | −1.563035 | −1.874953 | 25 | +2.068543 | +0.739204 |
| **All** | **153** | — | **−1.925832** | **−1.860335** | **109** | **+2.355575** | **+0.890440** |

The four groups sum to 153 and their slower-growth counts sum to 109. The Spearman correlation between baseline log productivity and paired period contrast is **+0.133214**, with **no hypothesis test or population inference claimed**. All four quartile medians are negative, but they are **not monotone**: Q3 has a much smaller median decline than Q1, Q2 or Q4. The result therefore does **not** support a simple uniform or monotone baseline-productivity gradient.

## Critical internal AI review
1. The stratifier P2000 is itself an input to E, which is subtracted in d; **mathematical coupling and regression to the mean** can generate associations. Do not interpret the weak Spearman correlation as an economic mechanism.
2. The short 2019–2023 window is not comparable in volatility to the 19-year 2000–2019 window; pandemic-era shocks and country-specific data revisions are not controlled.
3. Quartile boundaries are chosen from the same selected 153 economies, not world-representative or weighted by agricultural workers.
4. No independent ILOSTAT historical employment vintage, independent producer-level productivity data or causal identification is added.
5. Report the analysis as exploratory heterogeneity only, with **no new estimator or priority/novelty claim**. Keep **MAJOR REVISION / NO SUBMISSION**.

**Verification:** all statistics computed directly in the connected GitHub session from the full 19,922-character CSV with quoted-field handling, and no external data or fabricated observations. No GitHub Actions run or Word artifact is claimed for this calculation.

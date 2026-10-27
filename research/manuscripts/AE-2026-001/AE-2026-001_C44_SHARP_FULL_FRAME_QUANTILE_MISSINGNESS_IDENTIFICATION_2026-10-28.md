# AE-2026-001 C44 — Sharp full-frame quantile non-identification under 60 missing growth rates

**28 October 2026 | Internal AI quantitative audit | MAJOR REVISION / NO SUBMISSION**

## New calculation and reproducibility

This is a *new* order-statistic extension of C36, recomputed independently from the source-locked 2026 WDI country CSV (217 nonaggregate economies; Git blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`; SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`). There are **157** observed strictly positive 2000/2019 endpoint pairs and **60** missing rates. Growth is `100*ln(P2019/P2000)/19`, annual log-percentage points.

Define the finite-frame nearest-rank p-quantile as the `k=ceil(217*p)`th ordered value among **all 217** economies. With 60 unrestricted unknown rates, the **sharp infimum** is `-infinity` if `k<=60`, otherwise observed order statistic `x_(k-60)`. The **sharp supremum** is `+infinity` if `k>157`, otherwise `x_(k)`. Infinity means arbitrarily extreme possible values, **not** a measured infinite rate. Every finite endpoint is attainable by assigning unknown rates sufficiently below or above all observed values.

| p | Rank k | Sharp lower infimum | Sharp upper supremum | Observed boundary witness |
|---|---:|---:|---:|---|
| 10% | 22 | unbounded below | -0.064478 | SLV (upper) |
| 25% | 55 | unbounded below | 1.629363 | BTN (upper) |
| 50% | 109 | 1.423959 | 3.689876 | LBR (lower), SWE (upper) |
| 75% | 163 | 3.488990 | unbounded above | TUN (lower) |
| 90% | 196 | 4.838383 | unbounded above | UKR (lower) |

All numeric values are annual log-percentage points, rounded for display. The median matches C36 and is **not** counted as a new discovery. The new result is that **neither tail quartile is bounded on both sides**, despite the median's finite interval; no finite two-sided full-frame interquartile-range identification follows from these 157 observations alone.

## Scientific implication and limits

The previously reported observed-sample quartiles must **not** be labelled quantiles for all 217 economies. At 27.65% missingness, the finite-frame 25th percentile can be arbitrarily low and the 75th percentile arbitrarily high without violating a single observed country value. This is an assumption-free sensitivity statement, **not** evidence that missing economies actually have extreme growth, a population distribution, a confidence interval, a missingness mechanism, or a causal claim.

Reproduce with `python research/manuscripts/AE-2026-001/analysis/c44_sharp_quantile_missingness_bounds.py research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`. The script checks the original SHA256, 217 unique keys, 157/60 mask, and the C36 median endpoints. The calculation was independently executed against the full source CSV in this cycle; **execution of the newly committed Python file is not yet separately confirmed**.

**Remaining primary blockers:** historical WDI release identity; ILOSTAT 2024/2025 employment archives and source dependence; direct countryatlas benchmark; publication-level novelty; substantive human author review and disclosures. This secondary sensitivity does not move the manuscript beyond MAJOR REVISION / NO SUBMISSION.

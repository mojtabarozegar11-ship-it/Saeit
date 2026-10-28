# AE-2026-001 C22 — Numerically matched countryatlas CAGR convention versus annualized log growth

**26 October 2026 | Direct calculation from source-locked 2026 official WDI observations | No R package execution; MAJOR REVISION / NO SUBMISSION**

## Why this is a narrow, real benchmark, not a claim of novel methods

The documented `countryatlas` R package v3.0.0 provides `growth_rate(data, value, type="cagr")`, an ordinary compound annual growth rate from the first observed year, and `compare_vintages(indicator, vintages, year, countries)`, which already compares same-year WDI indicator levels between releases. The relevant primary documentation is:

- https://www.rdocumentation.org/packages/countryatlas/versions/3.0.0/topics/growth_rate
- https://pursuitofdatascience.github.io/countryatlas/reference/compare_vintages.html

**We did not install or execute countryatlas.** We implemented its *documented CAGR mathematical convention* on the same source-locked two-endpoint WDI observations used in the AE manuscript and compared the numerical output to AE's natural-log growth. This is a **formula-equivalent numerical benchmark**, **not** the still-missing direct execution of `countryatlas::compare_vintages` on the identical 2024/2025/2026 archive files.

## Primary data and exact estimands

Source: `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`, 217 distinct nonaggregate economies, expected SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`. No new observations were acquired.

For a strictly positive same-economy endpoint pair `P_start, P_end` and `T=end-start` years:

- **AE log growth** in log-percentage points/year: `g_log = 100 * ln(P_end/P_start)/T`.
- **Documented CAGR convention** in ordinary percentage points/year: `g_CAGR = 100 * [(P_end/P_start)^(1/T) - 1] = 100 * expm1(g_log/100)`.

These are **different numerical units/conventions** even though both are commonly described as annual percentage growth. Since `expm1` is strictly increasing, they preserve the same within-period country ranks and growth signs; their absolute values need not agree, especially with large changes.

## Newly calculated matched-country results

| Quantity | 2000–2019 | 2019–2023 |
|---|---:|---:|
| Strictly positive matched economies | **157** | **169** |
| Median annualized log growth, log-pp/y | **2.355575** | **0.975110** |
| Median conventional CAGR, %/y | **2.383538** | **0.979880** |
| Mean of country-level (CAGR minus log), pp/y | **0.060713** | **0.189026** |
| Median of country-level (CAGR minus log), pp/y | **0.034696** | **0.035003** |
| Economies with absolute convention difference >0.1 pp/y | **32** | **55** |
| Economies with absolute convention difference >0.5 pp/y | **0** | **10** |
| Country growth-sign agreement | **157/157** | **169/169** |
| Country rank ordering agreement | **identical** | **identical** |
| Largest absolute convention difference | **SVK +0.490912 pp/y** | **MLT +6.893831 pp/y** |

For **Malta (MLT), 2019–2023**, annualized log growth is approximately **−39.579082 log-pp/y**, whereas the mathematically corresponding CAGR is approximately **−32.685251%/y**. This large **6.893831 pp/y** difference is a *definition/scale conversion*, **not** a World Bank release revision, a second observation, or a measurement error. The high-leverage CAF and DJI cases also have nontrivial conversion gaps (approximately +4.362834 and +1.579035 pp/y, respectively).

The medians in the table are each computed across countries **after** applying the relevant country-level transformation. The mean of transformed country growth is not generally the transform of the mean log growth.

## Reproduction and execution evidence

- Source-locked code: `analysis/ae_2026_001_c22_countryatlas_cagr_vs_log_benchmark.py`.
- Branch-limited workflow: `.github/workflows/ae-2026-001-c22-countryatlas-formula-benchmark.yml`.
- **Actual GitHub Actions run:** https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40389894089 — `COMPLETED / SUCCESS`.
- **Real output artifact:** https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40389894089/artifacts/12681099650 — contains a JSON file with **all country-level values** and numerical checks.
- Source SHA, 217 unique economies, 157/169 cohorts, exact monotonic identity, zero sign disagreements, rank invariance, 32/55 >0.1 and 0/10 >0.5 thresholds, and SVK/MLT extreme cases are checked in CI.

## Editorial implications and unsolved gate

1. A large difference between log-pp and ordinary CAGR percentage points is **not** a historical WDI revision. Cross-study comparisons must harmonize this definition first.
2. The rank and sign invariance here is **mathematically guaranteed** by a monotone transform and is not empirical evidence of data reliability.
3. `countryatlas::compare_vintages` already supports release-level comparisons and unit-mismatch warnings. **Its actual numerical execution on the exact archived three-release AE dataset remains undone**, so this note does not close that stronger benchmark gate.
4. This result strengthens the measurement-language and prior-art checks, **not** novelty or causal claims. The historical 2024/2025 ILOSTAT sources, countryatlas full direct head-to-head, and independent AI final scientific adequacy gates remain open.
5. No publisher submission, author signature, journal review, live website change, expense or 149 GB download occurred.

**Decision: add a short measurement-convention sensitivity to AE; retain MAJOR REVISION / NO SUBMISSION.**

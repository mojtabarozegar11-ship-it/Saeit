# AE-2026-001 C24 — Actual countryatlas 3.0.0 R package head-to-head on source-locked WDI endpoints

**Date:** 2026-10-27. **Type:** newly executed original R package function benchmark, not another formula-only emulation. **Status:** confirmed successful GitHub Actions run, with country-level CSV artifacts. **Publication disposition:** MAJOR REVISION / NO SUBMISSION.

## Direct primary execution and provenance

- Exact official WDI country panel: `research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`, **217** nonaggregate economies, SHA256 **715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169**; `sha256sum --check` passed in CI before R.
- Actual package: **countryatlas 3.0.0** installed on **R 4.6.1** under Ubuntu 24.04.5; the exact version was asserted by `stopifnot(as.character(packageVersion("countryatlas"))=="3.0.0")`.
- The R function `countryatlas::growth_rate(long, ag_productivity, type="cagr")` was executed on each two-date country panel, using `iso3c`, `year` and `ag_productivity`. Each country was joined by **ISO3**, never by row order.
- [Successful GitHub Actions run 40407883759](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40407883759) (`completed/success`), job `direct-package-benchmark`, [artifact 12692315824](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40407883759/artifacts/12692315824). Artifact includes **three** CSVs: 2000–2019 country-level, 2019–2023 country-level, summary. Workflow [source](../../.github/workflows/ae-2026-001-c24-countryatlas-actual-r-head-to-head.yml) (root-relative path `.github/workflows/ae-2026-001-c24-countryatlas-actual-r-head-to-head.yml`).
- Artifact upload log recorded ZIP SHA256 **95849c574ce54c7ffea7a72f9dc0c6d1c03fc70891694509ee9cc4c473022943**. This is a GitHub upload-log checksum, not an independent local redownload verification.

## Results from the executed R package

| Matched interval | n economies | Median annual log growth (log-pp/year) | Median countryatlas CAGR (percentage points/year) | Maximum absolute difference (pp/year) | Package-vs-closed-form maximum absolute numerical error (proportion) | Growth-sign agreement |
|---|---:|---:|---:|---:|---:|---:|
| 2000–2019 | **157** | **2.3555753** | **2.3835381** | **0.4909116** | **2.220446e-16** | **157/157** |
| 2019–2023 | **169** | **0.9751105** | **0.9798802** | **6.8938312** | **2.220446e-16** | **169/169** |

The direct R output reproduces the earlier **C22 formula-only** cohort sizes and medians. This **closes the narrow outstanding question of whether the *actual* countryatlas 3.0.0 `growth_rate(type="cagr")` function matches the stated formula** for these specific positive two-date WDI panels. The maximum floating-point discrepancy is ~2.22e-16 in **proportional** units. It does **not** validate all countryatlas methods or a separate `compare_vintages` pipeline.

## Scientific interpretation and remaining gates

1. `countryatlas` CAGR and annualized log-growth use the **same endpoints** but a different nonlinear scale. Their numerical differences are **not WDI release revisions**, not ILOSTAT vintage revisions and not data errors.
2. C22 is **not** a direct package run; C24 **is**. Do not retroactively claim the earlier C22 executed R.
3. This is a **matched-country endpoint-function replication**, not a head-to-head test of `compare_vintages` on the three authentic 2024/2025/2026 WDI archives. **That full benchmark remains OPEN**; do not conflate 157/169 source-current cohorts with the 155-economy historical-vintage fixed cohort.
4. The direct agreement with an established R package is a **replication check**, not novelty, an original estimator, a causal identification strategy or independent employment data.
5. The 2024/2025 historical ILOSTAT datasets, vintage-specific classification definitions, independent source lineage and defensible novelty remain unresolved. No journal submission or author approval.

**Internal AI decision:** C24 actual R function benchmark **PASS**, but article AE remains **MAJOR REVISION / NO SUBMISSION**.

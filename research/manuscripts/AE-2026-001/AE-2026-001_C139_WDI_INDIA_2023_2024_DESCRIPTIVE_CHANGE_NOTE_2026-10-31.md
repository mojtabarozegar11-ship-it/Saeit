# AE-2026-001 C139 — India 2023–2024 WDI two-year descriptive change and evidence boundary

**2026-10-31 | R-01 | CODE / READY_FOR_REVIEW (descriptive data note only) | NOT a completed empirical article**

Source file: [C136 WDI two-year input CSV](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/AE-2026-001/AE-2026-001_C136_IND_WDI_TWO_YEAR_REPRODUCIBLE_INPUT_TABLE_2026-10-31.csv). Values were previously transcribed from the official World Bank WDI API, provider vintage **2026-10-08**; this run has **not** downloaded or hashed the original HTTP response, so this is not a raw-data archive or independent API verification.

| Indicator | 2023 | 2024 | 2024 minus 2023 | Meaning |
|---|---:|---:|---:|---|
| Agricultural employment share (% total employment; ILO-modeled WDI series) | 43.513581 | 42.354774 | -1.158807 percentage points | Model-based employment share, not a labor-force microdata observation |
| Agriculture/forestry/fishing value added (% GDP; WDI) | 17.656539 | 17.573580 | -0.082959 percentage points | National-accounts share, not farm profit |
| Employment-share minus GDP-share gap | 25.857042 | 24.781194 | -1.075848 percentage points | Difference between percentages with different denominators |
| Employment-share / GDP-share ratio | 2.464446 | 2.410139 | -0.054306 dimensionless | Descriptive share ratio, **not** an estimate of individual agricultural productivity |

**Reproduction formulas:** `gap_pp = employment_pct - value_added_pct`; `ratio = employment_pct / value_added_pct`; `delta = value_2024 - value_2023`. Input values retain full source-transcribed precision; displayed deltas round to six decimals. Country ISO3 **IND** only. Cross-indicator gaps/ratios are descriptive accounting contrasts, **not causal effects**, wage differentials, labor-productivity ratios, or econometric estimates.

**Source gates before manuscript results:** independently fetch and store exact WDI API response bytes + SHA-256, series identifiers and metadata; separately fetch ILOSTAT indicator definition and latest vintage; document revisions, coverage, comparability, uncertainty and any time-series model design. **BLOCKED** for source-archived scientific claims until those items exist. No journal submission or public CV publication.

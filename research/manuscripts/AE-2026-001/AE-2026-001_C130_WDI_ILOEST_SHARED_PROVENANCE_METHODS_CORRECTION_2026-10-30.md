# AE-2026-001 — official-series provenance correction (C130)
**Status:** METHODS INSERT READY_FOR_AUTHOR_REVIEW; empirical estimates BLOCKED pending authenticated raw source snapshots. **Checked:** 2026-10-30. **Owner:** R-01.

## Publication-ready methods replacement (subject to author verification)
Employment in agriculture is operationalized as the share of total employment classified in agriculture under the World Bank indicator `SL.AGR.EMPL.ZS`. The World Bank identifies the underlying source as the International Labour Organization's ILO Modelled Estimates (ILOEST), accessed through ILOSTAT. Thus a WDI observation and its matching ILOEST observation **must not be treated as two statistically independent confirmations** of the same national estimate. Differences between snapshots may arise from vintage, revision, metadata, extraction date or aggregation; they do not by themselves establish a substantive discrepancy. Country-level estimates are modeled, not direct counts of individual workers. India and Canada must be matched on country ISO3, calendar year, series definition and release vintage before any comparison. The numerator/denominator definitions and uncertainty must be confirmed from the original series metadata. This study will report descriptive differences in percentage points, not causal effects or policy impacts.

## Evidence-to-claim decision
| Evidence | Allowed | Not allowed |
|---|---|---|
| [World Bank indicator page](https://data.worldbank.org/indicator/SL.AGR.EMPL.ZS) identifies ILOEST/ILOSTAT as source | Label WDI and ILOEST as shared-origin modeled estimates | Count WDI and ILOEST as independent replications |
| [World Bank API V2 documentation](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392) | Define a reproducible raw JSON extraction with exact URL and retrieval timestamp | Invent observations when API download fails |
| [World Bank API date/country syntax](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581) | Use ISO3 country, fixed indicator and fixed year window | Mix 2023/2024 values from different vintages without disclosure |

## Data custody and acceptance gate
1. Fetch `https://api.worldbank.org/v2/country/IND;CAN/indicator/SL.AGR.EMPL.ZS?format=json&per_page=500&date=2010:2025` via an authorized client, storing the exact HTTP response bytes, response status, retrieval UTC and SHA-256. Record API pagination metadata.
2. Preserve World Bank series metadata, source date, units, licensing and ILOEST version. If any metadata or numeric observation is absent, mark `MISSING`; do not impute.
3. Retrieve a separately authenticated ILOSTAT raw snapshot and its release metadata if an actual cross-provider vintage comparison is intended. Compute cell-by-cell differences only after matching country/year/definition/release.
4. Generate a CSV with columns `country_iso3,year,indicator,wb_value,wb_source_release,wb_raw_sha256,ilo_value,ilo_source_release,ilo_raw_sha256,revision_difference_pp,verification_status`. `revision_difference_pp` is permitted only when both source vintages are known.
5. The previous provisional descriptive percentages remain quarantined until the two source snapshots are read back and checksummed. **No empirical claim or chart is approved by this document.**

**Next cursor:** obtain original raw WDI response + metadata + SHA, then ILOEST version and matched extraction; only then recompute India–Canada results. This document corrects a methodological independence error; it is not a dataset or statistical result.

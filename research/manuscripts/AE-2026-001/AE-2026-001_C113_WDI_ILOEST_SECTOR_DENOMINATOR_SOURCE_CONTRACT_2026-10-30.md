# AE-2026-001 — Source-locked agricultural employment / value-added contract (C113, 2026-10-30)

**Stage:** READY_FOR_REVIEW as an operational indicator-selection and extraction contract; **empirical paper BLOCKED** until dated country-year observations and source vintages are captured. No empirical findings are asserted.

## Primary-source-verified indicator dictionary

| Field | Employment share | Sector value-added share |
|---|---|---|
| WDI series | `SL.AGR.EMPL.ZS` | `NV.AGR.TOTL.ZS` |
| Name | Employment in agriculture (% of total employment), modeled ILO estimate | Agriculture, forestry, and fishing, value added (% of GDP) |
| Numerator | Modeled employed persons in agriculture, forestry and fishing | Sector value added, output minus intermediate consumption |
| Denominator | **Total employment**, not working-age population | **GDP**, not agricultural output or total employment |
| Producer | ILOEST/ILOSTAT distributed by World Bank WDI | World Bank WDI national-accounts indicator |
| Unit | percent of total employment | percent of GDP |
| Official locator | https://data.worldbank.org/indicator/SL.AGR.EMPL.ZS | https://databank.worldbank.org/metadataglossary/world-development-indicators/series/NV.AGR.TOTL.ZS |
| Data vintage | Current WDI page states upstream ILOEST accessed **2026-01-17**; this is **not** a guaranteed immutable 2026-01-17 snapshot | Record actual WDI retrieval timestamp and national-accounts revision vintage; do not assume identical revision schedule |
| Permissible comparison | Country-year employment *share*, if source/vintage verified | Country-year sector *value-added share*, if source/vintage verified |
| Prohibited claim | Headcount, job creation, survey-observed direct employment, causal effect | Farm revenue, labor productivity, causal economic effect |

The modeled employment share and the national-accounts value-added share are **different estimands**. A ratio of their percentages may be a descriptive relative-share index under explicitly matched sector/year/geography definitions, **not** directly measured labor productivity or proof of causation. Do not silently substitute WDI modeled employment for observed ILOSTAT labor-force-survey microdata.

## Data intake schema (one observation per country-year-series-vintage)

`country_iso3,year,series_id,unit,value,source_system,upstream_database,retrieved_utc,source_release_or_vintage,raw_response_sha256,source_url,missing_reason,qa_status`

- Enforce ISO-3 country code, integer year, known `series_id`, numeric percent in [0,100] or explicit missing, and a SHA-256 of **raw source bytes**. For missing values, leave `value` blank and record `missing_reason`; never interpolate by default.
- Never overwrite historical raw captures. Retain original JSON/CSV, source metadata, request URL, access time and a separate checksum manifest in authorized private storage.
- If an ILOEST vintage differs from the WDI download's current upstream release, mark `NOT_COMPARABLE_VINTAGE` until reconciled; avoid a false independent-replication claim.
- Use the existing read-only capture tool `research/quality_gates/ae_wdi_snapshot_capture_C110.py` for the employment series; its result is **CURRENT_API_AT_RETRIEVAL**, not a historical-vintage archive. Do not label it archival merely because the year queried is old.

## Reviewer decision gates

1. Record exact countries, period and both indicators with an explicit analysis plan and denominator definitions.
2. Capture **real** WDI country-year raw responses, hash and read back; preserve upstream ILOEST release identity separately.
3. Reconcile ISIC sector coverage, national-account revisions and missingness; document breakpoints and confidence limitations.
4. Only after the observed panel exists: pre-register/descriptively specify analyses and run source-sensitive estimates. Do not fabricate significance, DOI or publication status.

**Original sources inspected on 2026-10-30:** [World Bank/ILOEST employment indicator](https://data.worldbank.org/indicator/SL.AGR.EMPL.ZS); [World Bank WDI employment metadata](https://databank.worldbank.org/metadataglossary/World-Development-Indicators/series/page/9); [World Bank sector value-added metadata](https://databank.worldbank.org/metadataglossary/world-development-indicators/series/NV.AGR.TOTL.ZS).

**Next atomic action (R-01):** run existing capture tool for the agreed country/year, verify raw SHA and actual observed value, then capture a source-identifiable national-accounts counterpart in the same private dataset. No invented observations.

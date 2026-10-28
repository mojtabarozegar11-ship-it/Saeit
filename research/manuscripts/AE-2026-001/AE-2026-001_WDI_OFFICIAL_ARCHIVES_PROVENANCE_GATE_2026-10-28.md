# AE-2026-001 — Original WDI archive-release locator, comparison specification and provenance gate
**Date:** 2026-10-28. **Status:** official release paths IDENTIFIED; actual historical bytes NOT ACQUIRED; compare_vintages NOT EXECUTED; manuscript remains MAJOR REVISION / NO SUBMISSION.

## Verified official release catalog
The World Bank's official [WDI Archives page](https://datatopics.worldbank.org/world-development-indicators/wdi-archives.html) explicitly lists the following historic release months. The archive contains compressed Excel files rather than an automatically preserved historical version of the live API:

| Requested release | Official archive download URL identified from official catalog | Status and limitations |
|---|---|---|
| 2024-12-16 | https://databank.worldbank.org/data/download/Archive/WDI_excel_2024_12_16.zip | **Locator verified**; ZIP not downloaded; hash absent |
| 2025-12-19 | https://databank.worldbank.org/data/download/Archive/WDI_excel_2025_12_19.zip | **Locator verified**; ZIP not downloaded; hash absent |
| 2026-10-08 | https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_EXCEL_2026_10_08.zip | **Locator verified**; ZIP not downloaded; hash absent |

**Important:** These links were identified on the original official site, but the download endpoint could not be read through the current web tool and there is **no assertion** that the actual ZIP bytes or spreadsheet contents have been checked. The current-source API-derived 2026 panel committed in the repository is not guaranteed to match the October 2026 archive, and must not substitute for it without an exact comparison.

- Target [World Bank series](https://data.worldbank.org/indicator/NV.AGR.EMPL.KD): **NV.AGR.EMPL.KD**, agriculture, forestry and fishing value added per worker (constant 2015 US$). The World Bank series currently attributes sources to **World Bank WDI and ILOSTAT**. This series is a derived/composite statistic, and a WDI/ILOSTAT agreement must not be represented as independent validation if the underlying ILO data enter both.
- World Bank warns explicitly in its [WDI Database Archives](https://databank.worldbank.org/databases/archives) that codes can be reused for different constant-price base years or valuation bases. **Verify unit, base-year and construction metadata per vintage**; equal indicator code is insufficient to declare comparability.
- [ILOSTAT data portal](https://ilostat.ilo.org/data/) provides current bulk-download and web-service access, not by itself a verifiable 2024/2025/2026 historical snapshot. Do not label a current ILOSTAT pull an independent earlier release.

## Required 3-vintage execution (not yet done)
1. Obtain the exact **three original official archives** in private controlled storage. Record HTTP source, response date, bytes, SHA-256, ZIP integrity, filenames and license. Do **not** put 36–80MB proprietary or unreviewed archive blobs into a public Git repository.
2. Inspect the original workbook sheets, indicator code and value labels, publication metadata and base year, unit scaling, country classification and historical series coverage; reject any unverified base-year mismatch.
3. Extract an immutable long-form normalized table `(vintage_id, country_code, indicator_code, year, value, original_file, original_sheet, cell_or_row)`; verify no duplicate keys, no hidden aggregate rows, no coercion of missing values to zero.
4. Evaluate the exact same country/endpoint pairs (2000, 2019, optionally 2023) by **fixed common cohort** and, in a separate reported result, a release-specific observed cohort. Calculate (g_i=100\ln(y_{i,2019}/y_{i,2000})/19) on strictly positive measured endpoints only. Report n, median, mean, rank and missingness separately.
5. Report vintage-to-vintage changes at the **country-series-value** level before discussing trend robustness; preserve methods and missingness CSVs and unit tests. Do not conflate the separate current 217/157/153 country cohorts from C13/C14 with this yet-unconstructed historical panel.
6. For validation against ILOSTAT, obtain truly independently archived original **employment** inputs, their release date and ISIC definitions. Recalculate the agricultural employment denominators independently only when value-added and labor measure units/concepts align; otherwise explicitly classify same-source agreement.

## Current gate outcome
**DONE:** authoritative primary-source archive paths found and critical base-year / shared-source caveats established.  
**NOT DONE:** original archive bytes, historical SHA-256, 2024/2025/2026 source extraction, verified ILOSTAT historical vintage, `compare_vintages` execution or journal-ready novelty evidence.  
No synthetic reconstruction, no claim of real archive data, no externally peer-reviewed article, no release/submission.

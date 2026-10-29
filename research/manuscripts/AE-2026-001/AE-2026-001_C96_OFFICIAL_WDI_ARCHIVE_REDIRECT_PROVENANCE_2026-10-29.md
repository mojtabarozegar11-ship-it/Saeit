# AE-2026-001 — WDI official-archive redirect and source-vintage evidence, C96
**Owner:** R-01 | **State:** READY_FOR_REVIEW for archive retrieval; historical estimates remain BLOCKED | **Date:** 2026-10-29

## New source-level verification
The [World Bank WDI official archive index](https://datatopics.worldbank.org/world-development-indicators/wdi-archives.html) explicitly lists December 2024, December 2025 and October 2026 historical archive links. The archive index describes each as compressed Excel data (typical 36–80 MB). The following are *archive locations*, **not retrieved/hashed data**:

| Release | Official index href (source URL) | Observed redirect/final archive target | Verification |
|---|---|---|---|
| 2024-12-16 | https://databank.worldbank.org/data/download/Archive/WDI_excel_2024_12_16.zip | https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_excel_2024_12_16.zip | World Bank archive index link and redirect target checked 2026-10-29; ZIP bytes NOT acquired |
| 2025-12-19 | https://databank.worldbank.org/data/download/Archive/WDI_excel_2025_12_19.zip | https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_excel_2025_12_19.zip | World Bank archive index link and redirect target checked 2026-10-29; ZIP bytes NOT acquired |
| 2026-10-08 | https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_EXCEL_2026_10_08.zip | same URL | Official October archive link checked 2026-10-29; ZIP bytes NOT acquired |

**Material correction to acquisition instructions:** The 2024/2025 archive links redirect to the World Bank files host; an acquisition manifest should preserve **both** the official index href and the resolved final URL, rather than treating a redirected download as a different independent source. The existing `research/quality_gates/ae_wdi_three_vintage_offline_gate.py` checks the official index href and local archive bytes; it does not authenticate an HTTP redirect history, and its synthetic passing tests do not establish historical series.

## Fail-closed release criteria
- No historical country-year value, WDI revision estimate, growth benchmark, or countryatlas comparison can be reported from these URLs alone. **Real ZIP bytes, retrieval time, original SHA-256, CRC, workbook metadata and indicator/country-year extraction are all still missing.**
- The current WDI API is a *current-source snapshot*, not a reproducible historical 2024/2025 archive. Historical WDI series and independently versioned ILOSTAT releases must be labelled separately; same-source correlations are not independent validation.
- For a reproducible benchmark, fix the country/indicator/year cohort *before* observing changes, retain missingness by vintage, compare matching units/base-year definitions, and record every original archive checksum. Do not impute missing vintages or substitute the latest WDI for earlier snapshots.
- A current countryatlas number, even if directly retrieved later, is a secondary display and not independent ground truth for a series derived from WDI/ILO. Direct page-level benchmark remains BLOCKED.

**Reproducibility now:** Follow the three hrefs in the official index and inspect the redirects; do not assert ZIP integrity from the HTTP link. **Next exact step:** acquire one allowed 2024 WDI ZIP through the existing permitted offline workspace (not VPS), compute its SHA-256 and inspect workbook metadata before any numerical comparison.

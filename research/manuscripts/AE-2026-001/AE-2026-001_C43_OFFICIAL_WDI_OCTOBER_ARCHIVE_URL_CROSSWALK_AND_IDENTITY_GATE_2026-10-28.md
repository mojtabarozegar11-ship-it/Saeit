# AE-2026-001 C43 — official World Bank WDI October archive link crosswalk, not a byte-level revalidation

**28 October 2026.** Independent source navigation against the World Bank's official [WDI Archives index](https://datatopics.worldbank.org/world-development-indicators/wdi-archives.html). This is **primary archive URL provenance**, not a new WDI data download, not a countryatlas `compare_vintages` run, and not an ILOSTAT vintage archive.

## Three official index targets
| Study comparison release | Exact World Bank archive target linked by official index | Match to manuscript provenance |
|---|---|---|
| October 2024 | [WDI_excel_2024_10_24.zip](https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_excel_2024_10_24.zip) | Date **2024-10-24** agrees with the historical source recorded in manuscript §2.1 |
| October 2025 | [WDI_excel_2025_10_08.zip](https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_excel_2025_10_08.zip) | Date **2025-10-08** agrees with the historical source recorded in manuscript §2.1 |
| October 2026 | [WDI_EXCEL_2026_10_08.zip](https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_EXCEL_2026_10_08.zip) | Date **2026-10-08** agrees with the 2026 API source-update label; **ZIP is not the committed 2026 API CSV** |

**Source retrieval caveat:** The official index exposes these exact link destinations, but attempts to fetch the ZIP payloads through the public web reader were not successful (redirect restrictions / binary ZIP unsupported). Therefore **file-byte hashes, Excel worksheet contents, release equivalence and fixed-cohort numerical values were NOT reverified in this cycle**. Existing manuscript 2024/2025 SHA256 digests and original CI runs remain historical evidence, not new successes. Never infer that the 2026 October ZIP is byte-equivalent to the API CSV or that API source-57 vintage IDs correspond one-to-one to these ZIPs.

## Impact on source identity and author review
- The primary paper's three dates can now be linked to **exact official archive filenames** rather than only a generic WDI archives landing page. This closes a narrow **URL/date attribution gap**, not the statistical source identity gap.
- The [C42 benchmark implementation](analysis/countryatlas_two_archive_plus_locked_2026_snapshot_benchmark.R) still requires historical API release labels, a validated fixed 155-country cohort, and execution; a valid `compare_vintages` comparison **cannot be asserted**.
- Historical ILOSTAT 2024/2025 employment snapshots and numerator/denominator vintage attribution remain unresolved; current ILOSTAT RDS cannot be substituted silently.
- No manuscript novelty, author approval, journal submission, DOI, human review or new numerical result is implied.

**Internal AI decision:** keep AE in MAJOR REVISION / NO SUBMISSION.

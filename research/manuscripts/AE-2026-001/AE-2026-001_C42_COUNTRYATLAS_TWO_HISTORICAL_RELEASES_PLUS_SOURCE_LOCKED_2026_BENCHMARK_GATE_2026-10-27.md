# AE-2026-001 C42 — Fix benchmark release-identity trap: two API archives + source-locked 2026 CSV

**Date:** 27 October 2026. **Status:** substantive benchmark implementation correction, **NOT an executed numerical countryatlas benchmark**, historical archive identity proof, or new scientific finding.

## Primary documentation inspected
- Official countryatlas `compare_vintages` function documentation (website currently documents v4.0.0): https://pursuitofdatascience.github.io/countryatlas/reference/compare_vintages.html — signature `compare_vintages(indicator, vintages, year = NULL, countries = NULL)`, returns `iso3c, country, vintage, value, revision, rel_revision`; explicit `year` required for our two-endpoint comparison.
- Official `wdi_vintages()` documentation: https://pursuitofdatascience.github.io/countryatlas/reference/wdi_vintages.html — returns `vintage, id, label` for **API source 57**. Documentation examples show 2025-10 and 2026-07, but examples do **not** establish the presence or absence of a live 2026-10 release. The archive list must be queried in the pinned package environment.
- Existing project script [countryatlas_exact_endpoint_vintage_benchmark.R](analysis/countryatlas_exact_endpoint_vintage_benchmark.R) requires **three** API vintages, including a presumed 2026-10, while the source-locked study actually used two historical XLSX ZIP archives and a separate October 2026 WDI API CSV snapshot. Equal month names **do not prove** API-vintage and ZIP byte equivalence.

## Executable correction prepared
New [two-archive plus source-locked 2026 benchmark script](analysis/countryatlas_two_archive_plus_locked_2026_snapshot_benchmark.R):
1. Pins **two** independently available historical API release labels (not a fabricated third API release).
2. Requires an **independently source-verified fixed cohort of exactly 155 ISO3 codes**; never constructs a fake cohort.
3. Requires the **existing 217-row 2026 WDI CSV**, checks its exact previously recorded SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`, then extracts 2000/2019 growth for the 155 verified IDs.
4. Uses countryatlas `compare_vintages` separately for **2000 and 2019**, requires 155 positive endpoint pairs for each historical release, rejects duplicates and missing keys.
5. Outputs aligned 155-economy historical API growth, 2026 source-locked growth and three paired revisions. It refuses to silently substitute current API values.
6. Prints **EXPLORATORY** and **API-vs-ZIP identity unverified**; a release API archive is not necessarily byte-equivalent to the historical 2024/2025 XLSX ZIPs.

## Remaining blocking evidence
- The 155-ISO3 cohort CSV must be generated and checked against the original 2024/2025 source-hashed XLSX archives and the 2026 snapshot, rather than guessed from the 157-economy 2026-only panel.
- The two pinned historical API release labels must actually be returned by `wdi_vintages()` in countryatlas 3.0.0.
- The R script must be executed in a documented environment, output rows inspected and benchmark values reconciled to original ZIP-derived country-level growth. **Not executed in this cycle.**
- Historical ILOSTAT 2024/2025 employment sources, historical numerator/denominator attribution, source dependence and a defensible publication novelty claim remain open.

**Critical AI decision:** Correcting a reproducibility script is not completing a benchmark or making a manuscript publishable. AE remains MAJOR REVISION / NO SUBMISSION. No invented release, data, DOI, author approval or submission.

# AE-2026-001 C49 — strict source identity for the countryatlas comparison

**28 October 2026 | Methods/code correction, not a completed benchmark. MAJOR REVISION / NO SUBMISSION.**

## Actual correction
The existing `analysis/countryatlas_two_archive_plus_locked_2026_snapshot_benchmark.R` now refuses to run unless:
1. An independently reviewed 155-country cohort CSV is provided with an exact 64-hex-character `AE_COHORT_SHA256`, and its bytes match that SHA256. A user-supplied checksum alone cannot establish independent scientific validation of the cohort.
2. Both historical API vintage names exist in `countryatlas::wdi_vintages()` **and** their API `id` values exactly equal the expected `YYYYMM` codes. An archive month name is not proof that a local dated ZIP is byte-identical to the API release.
3. `compare_vintages()` returns without warnings for both year 2000 and 2019. In particular, any unit-mismatch, missing-release or incomplete-data warning aborts the benchmark rather than allowing a silent numerical comparison.
4. The source-locked 2026 snapshot SHA256, the 155 matched country keys and all positive endpoints still pass the prior gates.

## Primary comparator documentation checked
The current public documentation for **countryatlas 4.0.0** states that `wdi_vintages()` returns `vintage`, `id`, and `label`, with API release IDs such as `202510`. It also specifies `compare_vintages(indicator, vintages, year, countries)`, returning one row per country/release, and warns about possible rebasing of units across vintages. Sources:
- https://pursuitofdatascience.github.io/countryatlas/reference/wdi_vintages.html
- https://pursuitofdatascience.github.io/countryatlas/reference/compare_vintages.html

**Important version distinction:** the repository script requires countryatlas **3.0.0**, whereas the currently rendered website documents **4.0.0**. This source inspection is *not* a successful 3.0.0 runtime validation. No R executable or verified 155-country cohort was available in this run, and no API/ZIP identity is asserted.

## C13/C14 recovered as historical controls (NOT new findings)
- [C13](AE-2026-001_C13_FOUR_ECONOMY_2023_ATTRITION_ORDER_STATISTIC_AUDIT_2026-10-26.md), Git blob `18b9ad91b521589ecba2629162d5c738737e337b`: four 2023-attrited economies SDN, SYR, PSE, UKR; 157-to-153 balanced-sample median preserved by order-statistic cancellation.
- [C14](AE-2026-001_C14_THREE_ENDPOINT_AVAILABILITY_MASK_CENSUS_2026-10-26.md), Git blob `ec5fb36b573e068a56d1c6fd4b32c48d4cb45fab`: 217-case availability mask counts `000=43, 001=0, 010=0, 011=16, 100=1, 101=0, 110=4, 111=153`.
These analyses are **2026-only** and cannot substitute for the three-release historical 155-country cohort or an ILOSTAT historical employment archive.

## Unresolved
Historical WDI archive byte identity and 155-country cohort independent approval; ILOSTAT 2024/2025 and current-source provenance; overlap of WDI and ILOSTAT source; execution of the exact countryatlas benchmark; novelty over existing database-revision studies; human author approval. **NO SUBMISSION.**

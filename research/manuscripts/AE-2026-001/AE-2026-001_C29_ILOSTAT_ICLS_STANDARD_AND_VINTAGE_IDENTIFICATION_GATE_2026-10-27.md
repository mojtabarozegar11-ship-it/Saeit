# AE-2026-001 C29 — Primary ILOSTAT definition and historical-vintage identification audit

**Date:** 27 October 2026. Internal primary-source methods audit; **not** a newly downloaded ILOSTAT historical vintage, proof of any individual country's standard, or a causal explanation for WDI revision.

## New primary-source verification
The ILOSTAT explanatory article "New ILO database updates work-related indicators to meet latest standards" (2022) documents **nonuniform national adoption** of the employment/work-statistics framework: the 13th International Conference of Labour Statisticians (ICLS, 1982) and the revised 19th ICLS (2013) concepts are not necessarily interchangeable. The ILO explicitly distinguishes its WORK database built around 19th-ICLS concepts from LFS and related series based on earlier concepts; implementation timing varies by country. Primary: https://ilostat.ilo.org/blog/new-ilo-database-updates-work-related-indicators-to-meet-latest-standards/

The ILOSTAT data access portal describes current explorer, web service and bulk CSV downloads, but its public data landing page **does not itself document access to immutable 2024 and 2025 versions of the specific `EMP_TEMP_SEX_ECO_NB_A` table**. Primary: https://ilostat.ilo.org/data/ . This is **not evidence that such archives do not exist**; their accessible, date-stamped source bytes remain unverified.

The ILO's official `Rilostat` package documentation states that datasets and metadata published as of 3 May 2023 are generally **CC BY 4.0 unless otherwise indicated**, requiring appropriate attribution. Primary: https://github.com/ilostat/Rilostat . License status for a specific historical archive and its accompanying metadata still requires checking; a package's BSD license is distinct from its data license.

## Direct consequence for AE's estimand
The current ILOSTAT file `EMP_TEMP_SEX_ECO_NB_A` and 2026 WDI-implied employment levels are **not statistically independent validations** merely because they were downloaded separately: WDI uses ILOSTAT in its indicator source lineage. Furthermore, differences between country-year records may reflect standard, coverage, economic-activity classification, source selection, or update date. **No one mechanism can be assigned without country-specific metadata and date-stamped component releases.**

Historical 2024/2025 WDI **composite indicator** archives do permit descriptive comparison of the published indicator at a fixed endpoint and country set. They do **not** by themselves identify how much revision comes from value added versus workers or 13th/19th-ICLS implementation. Distinguish the following:
- **Identified:** paired changes in `NV.AGR.EMPL.KD` published growth estimates for 155 fixed economies across dated WDI releases.
- **Not identified:** independent ILOSTAT employment replication for the 2024/2025 vintages, country-specific changes in 13th/19th-ICLS classification, and attribution of the WDI revision to numerator or denominator.

## Internal critical review and manuscript edit rule
A narrow methods/data note is feasible **only if** the manuscript labels its employment exercise as a current-source consistency check, explicitly warns about ICLS definition drift, and avoids claiming that archival 2024/2025 ILOSTAT worker denominators were retrieved. It must not infer employment-standard changes from the observed 5.805% median discrepancy. Journal novelty remains to be evaluated against existing revision studies and `countryatlas::compare_vintages`. **MAJOR REVISION / NO SUBMISSION**; author contribution and publication approvals remain outstanding.

This is a **new documented source-interpretation finding** in this cycle, not an empirical data collection or a count of newly verified country-level classification transitions.

# AE-2026-001 C39 — countryatlas source-57 release identity and endpoint matching gate

**27 October 2026 — official package-documentation audit; not a completed numerical benchmark.**

## Verified API behavior
- The countryatlas documentation says that WDI archives are queried through the **World Bank WDI Database Archives API source 57**. Function wdi_vintages() returns an API vintage code such as 202510 for the label "2025 Oct", not a hash of a locally downloaded WDI archive ZIP. Source: https://pursuitofdatascience.github.io/countryatlas/reference/wdi_vintages.html .
- The currently published documentation example lists 2025-10, 2025-12, 2026-01, 2026-02, 2026-04 and 2026-07. This is an **illustrative tail of releases**, not evidence that 2024-10 is absent or that the last API release is necessarily the current 2026-10 dataset. The live release list was **not** executed.
- compare_vintages(indicator, vintages, year, countries) compares the **same indicator in a single year** across releases. Its attached revision summaries concern value changes, not 2000–2019 growth-rate changes. Source: https://pursuitofdatascience.github.io/countryatlas/reference/compare_vintages.html .
- fetch_indicator(source="wdi", indicator=..., years=c(2000,2019), vintage=...) is the documented path to pin the two endpoints to a specific API release. Source: https://pursuitofdatascience.github.io/countryatlas/reference/fetch_indicator.html .

## Exact scientific estimand and non-equivalence
The primary AE outcome for economy i and release v is g(i,v) = 100 * [ln(P(i,2019,v)) - ln(P(i,2000,v))]/19. Therefore:
1. First obtain both endpoints for each of 2024, 2025 and 2026 release definitions, using an **identical fixed country cohort**, positive finite values, same indicator NV.AGR.EMPL.KD and documented units.
2. Compute g(i,v) **within** each release and only then paired changes g(i,v2)-g(i,v1). Running compare_vintages once at year 2019 does **not** reproduce this estimand.
3. The API archive label "2025 Oct" cannot automatically be equated to the **8 October 2025 local ZIP**; likewise "2024 Oct" cannot automatically be equated to the **24 October 2024 ZIP**. Compare country-year values and units, metadata, release timestamp and local ZIP SHA256 to establish identity or explicitly label differences.
4. The API "current" endpoint in October 2026 is a moving live target. A documented historical 2026-07 API archive is not automatically equivalent to the study's 2026-10 live WDI extraction.
5. Any discrepancy between API and locally archived ZIP must be reported as a **release-identity difference**, not silently treated as a reproducibility failure of the original historical result.

## Unresolved gates
- No R countryatlas code executed and no source-57 endpoint data downloaded in this audit; no numerical three-vintage benchmark is claimed.
- The primary 155-economy 2024/2025/2026 comparisons still require independent matching of local archive ZIP content and API release identity.
- Official ILOSTAT 2024/2025 historical releases, independent worker-denominator provenance, best-source selection and disclosure of common-source dependence remain open.
- Historical ILOSTAT data cannot be reconstructed merely by fetching today's Rilostat bulk download; its current default cache is not a historical dated snapshot. See https://ilostat.github.io/Rilostat/reference/get_ilostat.html .

**Internal decision:** MAJOR REVISION / NO SUBMISSION. This is a method/provenance correction, not new WDI results, a validated benchmark or a final author approval.

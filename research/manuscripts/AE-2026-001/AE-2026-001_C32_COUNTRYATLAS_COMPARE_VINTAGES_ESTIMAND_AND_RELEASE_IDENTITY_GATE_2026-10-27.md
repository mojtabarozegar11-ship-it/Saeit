# AE-2026-001 C32 — countryatlas vintage comparator: estimand and release-identity audit

**27 October 2026. Source-documentation methods audit only. No new numerical benchmark, historical ILOSTAT download or claim of novelty.**

## Official package documentation checked

- https://pursuitofdatascience.github.io/countryatlas/reference/compare_vintages.html documents `compare_vintages(indicator, vintages, year = NULL, countries = NULL)`: a **single-year indicator-level** comparison across named WDI releases, returning per-country `value`, `revision` and `rel_revision`. `year=NULL` selects the latest mutually available year, **not** a 2000–2019 annualized growth contrast.
- https://pursuitofdatascience.github.io/countryatlas/reference/wdi_vintages.html documents `wdi_vintages()` as the list of release labels supported by the World Bank API archive (source 57). Its illustrative tail ends at 2026-07; this is **not proof** that an October 2026 API vintage is absent today.
- https://pursuitofdatascience.github.io/countryatlas/reference/growth_rate.html documents CAGR, a distinct convention from annualized log growth.

## Exact comparator design required

1. Query the actual installed package version and `wdi_vintages()` **at execution time**, checking availability of the archive labels corresponding to 24 Oct 2024, 8 Oct 2025 and the 8 Oct 2026 WDI snapshot. An archive ZIP timestamp is **not automatically equivalent** to a World Bank API archive release label.
2. For each eligible API vintage, call `compare_vintages('NV.AGR.EMPL.KD', vintage_labels, year=2000, countries=fixed_iso3)` and independently with `year=2019`. **Do not** use `year=NULL` or interpret a single-year level revision as a growth revision.
3. Join the two result tables on **ISO3 and vintage**, restrict to the **same 155 positive 2000/2019 countries** in all compared releases, and calculate `100*(ln(P2019)-ln(P2000))/19` by country and vintage.
4. Compare rowwise values, signs, ranks and paired differences with the existing source-hashed original ZIP/API pipeline. Confirm units and labels; honor any `countryatlas_unit_mismatch` warnings and never silently mix different constant-price bases.
5. If the API archive lacks an **identical release**, the package can provide only a **nearby-release sensitivity**, not an exact independent numerical reproduction of the original ZIP-snapshot comparison. Document the discrepancy and leave the exact head-to-head gate open.

## Critical conclusion

`compare_vintages` is a **single-year WDI-level comparator**, not an automatic three-vintage growth-rate validator. The earlier successful `countryatlas::growth_rate(type='cagr')` test validates the growth-rate convention for 2026-only endpoints, **not** this three-vintage archive equivalence. Both pipelines depend on WDI and are not independent sources of underlying economic observations. The actual three-vintage package execution remains **UNVERIFIED / NOT RUN** in this audit. AE remains **MAJOR REVISION / NO SUBMISSION**.
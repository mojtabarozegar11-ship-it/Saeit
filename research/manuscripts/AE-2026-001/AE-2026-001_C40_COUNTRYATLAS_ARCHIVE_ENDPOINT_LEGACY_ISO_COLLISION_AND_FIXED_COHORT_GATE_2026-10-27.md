# AE-2026-001 C40 — Direct upstream implementation audit: source-57 archive endpoint, legacy country codes, and fixed-cohort gate

**27 October 2026. Source-code audit of upstream countryatlas main branch (documentation currently 4.0.0), not a run of the 2024/2025/2026 WDI archive API or the project's pinned countryatlas 3.0.0. No new empirical estimates.**

## Upstream source evidence
- Upstream source file: https://github.com/PursuitOfDataScience/countryatlas/blob/main/R/worldbank.R ; public API documentation: https://pursuitofdatascience.github.io/countryatlas/reference/compare_vintages.html and https://pursuitofdatascience.github.io/countryatlas/reference/wdi_vintages.html .
- In the **currently inspected upstream source**, `wdi_vintages()` queries `https://api.worldbank.org/v2/sources/57/version?format=json&per_page=1000` and reads `source.concept.variable` release IDs. This is a source-code observation, not proof that any particular release is currently available.
- Archived observations use a **different API dialect** from the rolling current WDI API: `/sources/57/country/all/series/{indicator}/version/{YYYYMM}/time/YR2000;YR2019?format=json`. The code explicitly notes that the archive does not accept the current API's year-range syntax.
- The current upstream implementation normalizes historical country-code aliases **ADO→AND, ZAR→COD, TMP→TLS, ROM→ROU, KSV→XKX, WBG→PSE**, then resolves duplicate country-year keys by preferring already-ISO-coded rows. This can change which raw archive rows are matched. It does **not** establish that any of these aliases actually occurred in AE's specific 155-economy source-locked cohort.
- `compare_vintages` reports per-release levels at a **single year**; the AE estimand is a paired **two-endpoint log-growth difference**. Source code and published documentation agree on this distinction.

## Reproducibility failure modes and concrete decision
1. **Country identity:** compare archived API country IDs before and after alias normalization, and log any collision or duplicate with raw code, canonical ISO3, year, vintage and value. Never silently claim that two archive sources are byte-identical merely because the normalized ISO3 matches.
2. **Release identity:** `202410`, `202510` and any future `202610` are API month identifiers, not hashes of the original 24 October 2024, 8 October 2025 and dated October 2026 extracts. An archive label may be absent or may refer to a different within-month update. Do not substitute 2026-07 for 2026-10.
3. **Sample identity:** the proposed R benchmark requires a *verified original 155-ISO3 fixed-cohort CSV* and source metadata. The existing `analysis/countryatlas_exact_endpoint_vintage_benchmark.R` intentionally stops without that file and without three pinned available releases. A 157-economy 2026-only panel cannot be relabelled the 155-economy historical sample.
4. **Units:** check each vintage's original indicator label, constant-price base, positivity and data-revision timestamps before comparing. Any unit rebasing is a potential measurement comparability problem.
5. **Software identity:** upstream code/documentation is currently 4.0.0; the earlier executed CAGR benchmark used 3.0.0. An upstream source inspection is **not** proof of identical 3.0.0 behavior or of any successful source-57 data fetch.

## Result and open blocker
**New substantive source-code finding:** historical country-code canonicalization and duplicate-resolution are explicit parts of the comparator's implementation and must be incorporated into AE's release-identity audit. The direct three-vintage countryatlas numerical comparison, independent ILOSTAT historical vintages and any revision attribution to numerator versus employment denominator **remain unexecuted/unidentified**. A public World Bank archive endpoint was attempted through a web reader in this cycle but returned an access error; this is not evidence that the archive itself is down.

**Scientific disposition: MAJOR REVISION / NO SUBMISSION.** This is an additional provenance/confounding guard, not an original econometric method or author-approved manuscript.

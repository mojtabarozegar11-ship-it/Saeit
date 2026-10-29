# AE-2026-001 C104 — WDI historical vintage identity and rebase decision gate

**Owner:** R-01. **Stage:** READY_FOR_REVIEW source note; empirical analysis BLOCKED until actual independently checksummed archives and ILOSTAT extracts are present. **Date:** 2026-10-29.

## Primary-source evidence and actionable decision

The World Bank [WDI Archives by Year](https://datatopics.worldbank.org/world-development-indicators/wdi-archives.html) lists multiple **2026** editions (January, February, April, July, October) and historical archives. The [World Bank DataBank archives](https://databank.worldbank.org/databases/archives) warns that indicator codes can be reused after base-year or currency valuation changes, including `NY.GDP.MKTP.KD` for constant-USD GDP. Crucially, archive comparisons may display *current metadata* rather than the vintage-specific historical metadata. Therefore **equal indicator codes across two releases are insufficient evidence of equal measurement definitions**. This is a substantive comparability gate, not a claim that GDP or labor series changed in a specific country.

**Decision protocol:** for each (country, indicator, year, archive date), preserve official download URL, resolved final URL, local file SHA-256, archive edition, original series name, unit, base year, currency valuation, data source and retrieved metadata date. Refuse to calculate a revision delta when either release's historical unit/base is unverified or changed. A numerical delta may be calculated only for common nonmissing observations with matched definitions; label it `VINTAGE_REVISION_NOT_CAUSAL`. Keep a separate ILOSTAT source/definition/vintage ledger; do not silently join labor variables on code or country-year alone. Missing archival metadata => `BLOCKED_DEFINITION`, not zero revision.

**Runnable existing R-owned code:** [C101 offline WDI vintage panel gate](../../quality_gates/ae_wdi_vintage_panel_revision_gate_C101.py) computes complete-cohort deltas but only checks a user-declared `verified` boolean and SHA format; it does **not** authenticate archive bytes or historical definitions. Until the physical archives, checksums, source definition snapshots and ILOSTAT files are supplied, its output is a structural audit only and must not be presented as empirical findings. Next engineering task: verify archive bytes and historical series metadata before allowing revision estimates.

**Not asserted:** any country-year result, WDI/ILOSTAT dataset download, sample size, causal effect, paper submission or verified archive hash.

# AE-2026-001 C41 — Executed 2026-only country-code alias and collision check

**Date:** 2026-10-27. **Scope:** independently parsed source-locked 2026 WDI country panel only; NOT historical WDI archive reconciliation, not an executed countryatlas comparison and not proof of three-vintage identity.

## Input and method
Original repository CSV: [AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv](AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv), Git blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9` (2026-only 2000/2019/2023 observed values, 217 rows). This cycle independently parsed all 217 ISO3 keys, checked duplicate keys, checked all six historical aliases identified in [C40](AE-2026-001_C40_COUNTRYATLAS_ARCHIVE_ENDPOINT_LEGACY_ISO_COLLISION_AND_FIXED_COHORT_GATE_2026-10-27.md), and checked positivity of the 2000 and 2019 endpoints for their canonical counterparts.

| Legacy alias in upstream countryatlas | Canonical ISO3 | Legacy present in 2026 CSV | Canonical present | Canonical 2000+2019 eligible |
|---|---|---:|---:|---:|
| ADO | AND | 0 | 1 | No |
| ZAR | COD | 0 | 1 | Yes |
| TMP | TLS | 0 | 1 | Yes |
| ROM | ROU | 0 | 1 | Yes |
| KSV | XKX | 0 | 1 | No |
| WBG | PSE | 0 | 1 | Yes |

**Observed:** 217 unique ISO3 keys / 217 rows, **zero duplicate ISO3 keys**, **zero occurrences of six legacy aliases**, six canonical counterpart records, four of those six with positive 2000 and 2019 values. The overall 2026-only positive two-endpoint subset remains **157**, not the fixed historical **155** cohort.

## Interpretation and limitation
This closes a **narrow source-quality question for the archived 2026 panel file**: those six legacy aliases and duplicate ISO3 keys do not appear in that CSV. It **does not** show that the October 2024/2025 API archives or local Excel releases contain no historical aliases, or that the 155-economy three-vintage comparison is unaffected by normalization. The source-57 API vintage-to-ZIP identity, raw-to-canonical historical collisions, historical employment denominators and direct countryatlas benchmark remain unverified.

**Decision:** retain MAJOR REVISION / NO SUBMISSION. Do not present this diagnostic as a novel estimator, a historical archive benchmark, or an independent employment-source validation.

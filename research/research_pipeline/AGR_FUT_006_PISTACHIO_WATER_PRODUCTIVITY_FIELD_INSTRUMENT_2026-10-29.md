# AGR-FUT-006 — Pistachio irrigation-input productivity field-study instrument
**2026-10-29 | R-01 | READY_FOR_REVIEW as a blank, reusable field protocol; NO experimental observations or results**

## Research question and design
In established pistachio orchards, what is the association between **measured seasonal irrigation water applied** and **marketable dry-nut yield** after accounting for orchard, season, soil and management differences? The primary observational unit is an **orchard block × crop season**. The protocol is observational: neither causal effects nor randomized assignment are claimed. Record each eligible block before outcome observation to avoid selective case inclusion.

## Data collection schema (CSV header; zero rows collected)
```csv
study_id,site_pseudonym,block_pseudonym,season_year,block_area_ha,cultivar,tree_age_years,rootstock,soil_texture,irrigation_method,flow_meter_id,meter_calibration_date,season_start,season_end,opening_meter_m3,closing_meter_m3,other_irrigation_m3,measured_applied_m3,marketable_dry_nut_kg,nonmarketable_dry_nut_kg,harvest_moisture_pct,irrigation_input_wp_kg_m3,missingness_code,source_record_hash,reviewer_initials
```
**Do not enter real names, exact addresses, phone numbers, raw GPS or customer data in a public repository.** The blank schema above is public-safe. Filled data must remain in an authorized private store.

## Operational measurement rules
1. Record meter readings in m³ at the beginning and end of the *same* irrigation season; verify nondecreasing cumulative readings and calibration provenance. A meter reset or replacement requires a separately documented adjustment; never silently subtract across reset.
2. Compute `measured_applied_m3 = closing_meter_m3 - opening_meter_m3 + other_irrigation_m3` **only** if meter boundaries correspond to the block and no shared-line allocation ambiguity exists. Otherwise flag `METER_SCOPE_UNRESOLVED`.
3. Compute `irrigation_input_wp_kg_m3 = marketable_dry_nut_kg / measured_applied_m3` only for positive, validated irrigation input; this is **marketable dry yield per applied irrigation water**, not evapotranspiration-based WP or basin-scale conservation.
4. Use a consistent moisture-adjustment basis for marketed dry nuts; preserve the original weighbridge or processor record hash. Record harvest year and alternate-bearing history before fitting models.
5. Record all eligible blocks, including zero-yield and failed-meter cases; distinguish structural zero from missing. Recommended missingness codes: `NONE`, `METER_MISSING`, `METER_SCOPE_UNRESOLVED`, `HARVEST_MISSING`, `UNIT_UNVERIFIED`, `CONSENT_RESTRICTED`.
6. Never publish farm-identifiable raw data without permission; use pseudonyms and report sample flow (eligible, consented, metered, harvested, analyzed).

## Analysis acceptance gate
No effect estimate, p-value or publication-ready Results until a dated dataset with traceable measurements is received, units validated, missingness summarized, clustering by orchard/site addressed, and the author approves design and disclosure. Sensitivity analyses should compare complete cases with predeclared missing-data handling and account for cultivar, age, soil and seasonal rainfall where reliably measured.

**Next step:** F/B partners may collect approved, deidentified observations using this exact schema; R-01 then validates source hashes, unit consistency and analysis assumptions. This file is a ready-to-use collection instrument, not fabricated evidence.

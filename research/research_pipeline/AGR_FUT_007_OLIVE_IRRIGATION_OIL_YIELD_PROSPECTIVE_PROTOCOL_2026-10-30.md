# AGR-FUT-007 — olive irrigation input and marketable oil-yield prospective study
**R-01 · 2026-10-30 · usable blank data-collection protocol / READY_FOR_REVIEW · zero observed farms and zero study results.**

## Predeclared question and units
Among eligible established olive orchard blocks followed for **two consecutive harvest seasons**, how does measured *applied irrigation volume per hectare* relate to **marketable extracted olive-oil mass per hectare**, after accounting for site, cultivar, alternate bearing and management? The observational unit is **orchard block × harvest year**; irrigation events are nested within block-year, and blocks are nested within orchards. No randomized causal effect is claimed. Keep irrigation input distinct from crop evapotranspiration and from basin-level water conservation.

**Eligibility before enrollment:** stable mapped block area, same cultivar/rootstock where feasible, harvest and mill traceability, access to a calibrated block-specific meter or a documented proportional flow-allocation method, owner consent, and both productive and low-yield blocks (avoid survivor selection). Exclude no block solely because of zero production; record the reason for nonobservation.

## Immediately usable blank data schema
One row per block-year; no names, exact locations or raw customer information in the public template.

```csv
study_id,site_code,block_code,harvest_year,block_area_ha,cultivar,tree_age_years,trees_per_ha,alternate_bearing_prior_kg_ha,soil_texture,irrigation_method,irrigation_season_start,irrigation_season_end,calibrated_meter_code,meter_calibration_date,opening_meter_m3,closing_meter_m3,documented_other_irrigation_m3,allocated_shared_line_m3,meter_scope_status,irrigation_input_m3,olive_fruit_harvest_kg,fruit_moisture_pct,extraction_mill_batch_code,extracted_oil_kg,oil_yield_kg_ha,irrigation_input_kg_oil_per_m3,rainfall_mm,heat_days_over_threshold,harvest_method,missingness_code,record_provenance_sha256,review_status
```

## Field instructions and computation gate
1. Record **both** opening and closing cumulative flow readings on the same calibrated meter and at the same irrigation-boundary definition. For a dedicated meter, `irrigation_input_m3 = closing_meter_m3 - opening_meter_m3 + documented_other_irrigation_m3` only if readings are monotone and other water is independently documented. For shared lines, do **not** use a simple area ratio without measured allocation; otherwise `meter_scope_status=UNRESOLVED` and the input remains missing.
2. Harvested fruit mass and **extracted oil mass** must be distinct source records. A fruit-to-oil conversion factor must not be silently substituted for a mill ticket. If multiple blocks enter one mill batch without traceable segregation, record `MILL_ALLOCATION_UNRESOLVED` and withhold block-level oil outcomes.
3. `oil_yield_kg_ha = extracted_oil_kg / block_area_ha`; `irrigation_input_kg_oil_per_m3 = extracted_oil_kg / irrigation_input_m3` only for independently validated positive denominators. The latter is **applied-irrigation input productivity**, not consumptive-water productivity or causal water saving.
4. Preserve harvest-year weather observations, source, instrument and threshold for `heat_days_over_threshold`. Do not insert a temperature threshold after observing results; define one in the registered protocol before data analysis.
5. Predefine site/block clustering and the **alternate-bearing history**. Two consecutive harvests improve descriptive separation but do not identify causal effects by themselves. Record pruning, fertilizer, cultivar and oil-mill extraction process as potential confounders in a separate, privately stored management log.
6. Keep a sample-flow table: approached, eligible, consented, meter-valid, mill-valid, retained in analysis. Missingness codes: `NONE`, `METER_MISSING`, `METER_SCOPE_UNRESOLVED`, `MILL_ALLOCATION_UNRESOLVED`, `OIL_TICKET_MISSING`, `HARVEST_MISSING`, `CONSENT_RESTRICTED`, `UNIT_UNVERIFIED`.

## Pre-analysis decision rule (no data yet)
The primary descriptive model will treat oil yield (kg/ha) as outcome and applied irrigation (m³/ha) as exposure, with orchard/block random or fixed effects selected **before** analysis based on actual sample structure, year effects, cultivar and alternate-bearing history. Report a scatterplot with site-level strata and a complete-case/missingness sensitivity table; do not report a pooled causal coefficient if exposure allocation is nonrandom. Report medians and dispersion even if inferential modeling is underpowered. Sample size and detectable effect are **TBD pending a pilot variance estimate**, not invented. Publish no findings, p-values or DOI before actual consented, hashed measurements and author review.

## Data stewardship and handoff
All filled forms, consent records, meter images, harvest tickets and mill tickets stay in authorized **private** storage with access control and provenance SHA-256. Only blank templates and aggregate, deidentified, approved results may enter a public repo. The scientific owner R-01 receives a dated data dictionary, anonymized file and validation manifest before analysis; the field/partner owner decides actual collection and access.

**First usable action for a collector:** copy the header into a private CSV, register eligible block codes and calibration records before first meter reading. No real data or field visits are represented as completed by this file.

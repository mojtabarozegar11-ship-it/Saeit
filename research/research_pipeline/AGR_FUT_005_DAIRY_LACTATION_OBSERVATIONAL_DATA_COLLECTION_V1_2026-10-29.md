# AGR-FUT-005 — Dairy lactation observational data collection instrument
**Version:** R-01 C103, 2026-10-29. **Stage:** usable blank data instrument / protocol for ethics and farm review; **not a completed study**. No animal or human observations have been collected by R-01.

## Objective and unit of analysis
Estimate the association between feeding, parity, days in milk and **daily milk yield** at cow-day level within participating herds. The farm/herd is a clustering unit; repeated cow-days are **not independent animals**. Observational associations are not causal feed effects. Enrollment must use legitimate farm authorization and veterinary welfare protocols; no changes to ration or animal treatment are instructed by this template.

## Blank CSV header — enter actual records only
```csv
site_code,cow_pseudonym,observation_date,parity,days_in_milk,lactation_group,milk_kg_day,milking_sessions,feed_dmi_kg_day,feed_dmi_method,body_condition_score,body_condition_scale,temperature_c,heat_stress_index,health_event_flag,treatment_flag,feed_ration_code,milk_meter_id,meter_calibration_date,record_source,missingness_code,reviewer_status
```

## Field rules and validation
1. `site_code` and `cow_pseudonym` must be anonymous, locally assigned identifiers. No farm owner, GPS, employee, or customer data in public GitHub. The mapping key stays privately under farm control.
2. Primary key: (`site_code`, `cow_pseudonym`, `observation_date`). Date ISO 8601; one record per cow-day. Duplicate records are rejected pending reconciliation, not averaged silently.
3. `parity` is integer ≥1; `days_in_milk` integer ≥0, with calving date validated privately. Out-of-range values are flagged for verification rather than invented or auto-corrected.
4. `milk_kg_day` and `feed_dmi_kg_day` must be nonnegative physical quantities in **kg per cow per day**; milk meter and feed measurement method must be documented. Missing values are blank, never zero-filled.
5. `body_condition_score` is only interpretable together with `body_condition_scale` (e.g., 1–5). `heat_stress_index` requires its exact formula and sensor metadata; absent source = blank.
6. `health_event_flag` and `treatment_flag` are 0, 1, or blank unknown. Do not record sensitive staff or treatment details in this template. Veterinary oversight remains mandatory for welfare matters.
7. `missingness_code` permitted: OBSERVED, NOT_RECORDED, DEVICE_FAILURE, NOT_APPLICABLE, WITHHELD. `reviewer_status`: PENDING, VERIFIED, QUARANTINED. Raw records remain immutable; corrections are versioned.
8. Feed efficiency (`milk_kg_day/feed_dmi_kg_day`) may be calculated only when both are observed on compatible cow-day boundaries and DMI > 0. It is **not** feed conversion ratio for meat animals and is not energy-corrected milk without composition data.

## Analysis plan before any data collection
Define a prospective observation window and farm selection, pre-register inclusion/exclusion rules and outcome, document measurement uncertainty, and account for repeated observations and herd clustering (e.g., hierarchical models with farm/cow effects where data permit). Report cow-days, unique cows, farms, completeness by variable, reasons for exclusion, season and parity distribution. Compare sensitivity analyses with and without missing observations; do not impute without declared model and diagnostics. No efficacy, production gain or economic return claim until actual validated data, permissions, and appropriate analysis exist.

**Next:** F-01 or a farm research coordinator may adopt the template after authorization; R-01 will validate an anonymized data dictionary and missingness summary before drafting a scientific results section. No data/DOI/publication is represented as existing.

# AGR-FUT-009 | Dairy herd feed conversion and milk-yield measurement kit
**R-01 · 2026-10-30 · READY_FOR_REVIEW as a reusable blank field protocol; no animal data, enrollment, ethical approval, results, or DOI.**
## Primary question and scope
In consenting dairy herds, what is the within-herd association of **measured pen-level dry-matter intake (DMI, kg/day)** with **energy-corrected milk (ECM, kg/day)** over a prespecified 28-day observation window? Observational, not a randomized feed trial; no causal feed-savings claim. The analysis unit is **pen-day**, with cow-days and milking records nested within pen. Milk from individual cows cannot be divided by pen-level feed and reported as individual feed efficiency without individually measured feed intake.
## Ready-to-use private CSV header
```csv
study_id,herd_code,pen_code,observation_date,cows_present,cow_days,feed_batch_code,feed_offered_asfed_kg,feed_refused_asfed_kg,offered_dm_fraction,refused_dm_fraction,feed_intake_dm_kg,feed_intake_dm_kg_cowday,milk_weight_kg,milk_fat_percent,milk_protein_percent,milk_sample_method,ecm_formula_version,ecm_kg,ecm_kg_cowday,feed_efficiency_ecm_per_kg_dmi,feed_scale_calibration_date,milk_meter_calibration_date,temperature_humidity_index,health_event_count,feed_missing_reason,milk_missing_reason,observer_code,quality_flag
```
Store completed rows, farm identities, veterinary data and invoices only in an authorized private repository.
## Measurement rules
1. Record feed offered and orts with separately measured dry-matter fractions on the same basis. **DMI = offered_asfed × offered_DM_fraction − refused_asfed × refused_DM_fraction**. If feed is shared across pens without a valid allocation meter/scale, mark DMI missing, not allocated by head count.
2. Record pen cow-days from daily entry/exit counts. **DMI per cow-day = pen DMI / cow-days**, only when cow-days > 0. Treat the denominator as exposed animal-time, not the herd roster.
3. Record measured daily milk kg and lab fat/protein; identify laboratory method and exact ECM equation/version *before* calculating ECM. Do not mix 3.5%-fat-corrected milk with ECM. If no validated ECM formula has been prespecified, leave ECM blank and analyze raw milk kg only.
4. Retain zero production and clinically affected days with explicit flags; do not silently discard low performers. Specify feed composition, parity mix, lactation stage, season and heat exposure as confounders.
5. Prespecify a hierarchical model with herd and pen clustering, repeated-day correlation and missingness sensitivity; never treat repeated cow milkings as independent experimental herds. Report uncertainty intervals and observation counts.
## Collection acceptance gates
Consent and animal-welfare oversight as locally required; independent scale/milk-meter calibration evidence; time-aligned feed and milk records; traceable lab results; complete denominator ledger; preregistered quality thresholds; privacy review. **No valid field data exist in this artifact.** It is a usable blank collection instrument and analysis specification, not a published scientific finding.
## Rotation handoff
Owner R; next: select a participating herd only after consent and verify an ECM formula from a primary dairy nutrition source before entering values. No factory/VPS action.

# MR-2026-001 — pilot evidence-provenance crosswalk and proposed synthesis architecture (v0.1)

**Date:** 2026-10-24. **Purpose:** preserve distinctions across four *targeted-discovery* source audits before protocol freeze. **NOT** a systematic evidence synthesis, study-inclusion list, PRISMA record count, risk-of-bias consensus, or validated novelty claim.

## Cross-study audit (four known calibration examples; not a denominator)

| Study and DOI | Farmer-facing DSS actually offered? | Real-world decision/use evidence | Farm water/yield endpoint provenance | Economics/adoption boundary | Provisional role |
|---|---|---|---|---|---|
| Amini et al. 2025 — [10.1038/s41598-025-26567-z](https://doi.org/10.1038/s41598-025-26567-z) | Yes, participatory crop irrigation scheduling pilot. | Supervised pilot application on 8 monitored farms; workshops; no independent multi-season persistence established. | **M** published farm irrigation depths and harvest yields; **P** forecasts within the DSS. Treatment/control plot allocation and heterogeneity need review. | Participatory perceptions **S**; no audited farm net-profit ledger extracted. | Potential farmer-facing field pilot, pending final eligibility. |
| Silvestri et al. 2025 — [10.3390/s25237188](https://doi.org/10.3390/s25237188) | Analytical fuzzy DSS assessed retrospectively; farmer-facing deployment of both tested DSS policies not established. | Historical farmer irrigation baseline; DSS schedules evaluated as counterfactual simulations. | **M** baseline sector irrigation; **P** model-predicted DSS irrigation and critical dry days; **not M** for modeled saving. | Actual adherence and sustained adoption **U**. | Validation-only/context, not observed farmer adoption or field saving. |
| Schattman et al. 2023 — [10.1016/j.agwat.2023.108428](https://doi.org/10.1016/j.agwat.2023.108428) | Experimental soil-tension threshold scheduling; farmer-facing analytical DSS **not established**. | Research-plot treatment and separate farmer perceptions. | **M** trial irrigation and crop outcomes; **P** ET calculation. Three of four site-years had lower sensor-treatment water than soil-feel, not a universal effect. | Survey interest **S**, not observed adoption of a deployed DSS. | Negative-control example for separating sensor rules from farmer-facing DSS. |
| Darouich et al. 2024 — [10.3390/agronomy14010066](https://doi.org/10.3390/agronomy14010066) | Yes: IrrigaSys advice was available; farmers could choose their schedule. | Actual farmer scheduling compared with model-recommended schedules for 20 selected plots (2019 and **2022 per body**, versus **2020 per abstract**). | Farmer schedules recorded; modeled water balance and **P** crop yields for both farmer and optimized schedules. Independently metered volume **not verified** in this audit. | Gross-value indicators **P** using modeled yield and assumed price; no verified net profit or multi-year individual retention. | Close primary-study comparator that challenges any simplistic novelty claim. |

**No cross-study percentages, pooled effects, adoption rates, or counts of eligible studies are justified by this table.** Source details and unresolved discrepancies are recorded in the corresponding `PILOT_SOURCE_EXTRACTION*.md` documents on this draft branch.

## Testable analytical architecture (requires author approval)

**Question:** Among *real farmer-facing irrigation DSS deployments*, what evidence connects **(i) delivery of actionable advice**, **(ii) observed farmer scheduling/adherence**, **(iii) instrument-measured water/yield**, and **(iv) actually recorded economic outcomes**, rather than merely comparing field records with simulated optimal schedules?

Do not assume a positive answer or uniqueness. Earlier reviews may have addressed parts or all of this question.

### Noninterchangeable levels of evidence

1. **Availability/exposure:** tool deployed; recommendation generated; delivered to specific actor; read/received (each separate, denominator required).
2. **Decision use:** reported use, independently logged use, observed adherence, voluntary continuation, sustained multi-season retention (each separate, do not infer from service years).
3. **Biophysical endpoint:** real field meter/harvest **M**, reported farmer log **S/O** depending verification, model counterfactual **P**, unspecified **U**. Record numerator, denominator, unit, duration and comparator.
4. **Economic endpoint:** actual receipts and cost ledger **M/O**, farmer-reported perceived savings **S**, price-times-modeled-yield or hypothetical costs **P**. Do not label gross modeled value as net profit.
5. **Inference design:** randomized/controlled; within-farm nonrandomized; historical comparator; model counterfactual; no comparator. Classify **per endpoint**, since one paper can mix designs.

### Proposed evidence-map table columns

`study_id, DOI, country, crop, water_constraint_documentation, DSS_function, decision_actor, recommendation_delivery_evidence, use_adherence_denominator, observation_duration, comparator_type, endpoint_name, endpoint_unit, endpoint_source_location, provenance_MOSPU, measured_or_modeled, adverse_or_null_outcome, raw_data_access, selection_bias_notes, author_verified, second_human_verified`.

**Rule:** a row is a specific *study–endpoint–comparison*, not one row per paper. This prevents mixing a modeled economic result with a measured irrigation volume in the same outcome claim.

## Immediate unresolved questions

- **Darouich:** reconcile abstract 2020 vs body 2022; verify raw farmer irrigation metering, whether actual advice delivery/use was observed, and model-yield assumption. The discrepancy is documented, not an official publisher correction.
- **Amini:** obtain supplementary materials and exact WP unit/percentage definitions, check measured plot outcomes and allocation.
- **Silvestri:** retain possible adverse simulated critical-dry-day results, and do not upgrade modeled water saving to field observation.
- **Schattman:** validate whether any software delivered actual farmer-facing recommendations; if not, exclude from strict DSS-adoption stratum.
- **All:** execute licensed bibliographic searches and full-text screening before using these examples as an included-study set; compare with the included primary studies in Ara 2021 and Mabhaudhi 2023 and other overlapping reviews.

**Manuscript / submission status:** DRAFT / NOT SUBMITTED. No author approval, final manuscript, database exports, independent human screening, publisher receipt or Manuscript ID.

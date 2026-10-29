# AGR-FUT-004 — Broiler feed conversion: an auditable measurement protocol candidate
**R-01 rotating scientific portfolio** | 2026-10-29 | **State:** READY_FOR_REVIEW methodology artifact, DATA_PENDING / NOVELTY_UNVERIFIED. This is not a conducted trial, published article, approved animal study or claim of improved production.

## Research question
For existing authorized broiler-flock production records, how does reported feed-conversion ratio change when mortality adjustment, feed-return accounting, measurement intervals and final liveweight definitions are applied consistently? Primary unit is the **flock-cycle**, not the bird-day or individual bird; no new animal intervention or recruitment is authorized.

## Pre-analysis dictionary (must be completed before analysis)
| Variable | Definition and required unit | Provenance check |
|---|---|---|
| flock_id | Pseudonymized stable flock-cycle identifier | One-to-one with farm/site and cycle; retain private mapping |
| placed_n | Number of day-old chicks placed (count) | Dated placement ledger |
| harvested_n | Number sold/removed at marketing (count) | Dated dispatch and grading slips |
| mortality_n | Count of deaths by date | Daily mortality log; separate culls |
| feed_delivered_kg | Feed delivered to flock during cycle (kg) | Weighbridge/invoice, lot IDs and calibration |
| feed_returned_kg | Unconsumed feed returned at close (kg) | End-of-cycle inventory and scale record |
| marketed_liveweight_kg | Aggregate measured liveweight at sale (kg) | Calibrated scale/dispatch records |
| mortality_biomass_kg | Sum of weights of dead birds at death, where actually measured (kg) | Daily individual or batch weights; **never fabricate** |
| period_start/end | Inclusive dates and flock age in days | Placement/marketing timestamps |

## Estimands, not invented results
- Net consumed feed (kg) = delivered feed − documented returned feed ± **documented** inventory corrections. Reject negative net values.
- Commercial FCR = net consumed feed / marketed liveweight, provided both quantities are actually measured on matching flock/time boundaries.
- Mortality-adjusted FCR = net consumed feed / (marketed liveweight + independently measured mortality biomass), **only** when mortality biomass is measured; otherwise **NOT_ESTIMABLE**. Do not substitute assumed average bird weight.
- Deaths and culls are separate flows. `placed_n = harvested_n + mortality_n + culls_n + other documented exits` must reconcile; otherwise quarantine the flock-cycle.
- Feed purchase is not feed consumption; hen-day, broiler FCR and country-level poultry-stock metrics are noninterchangeable.

## Minimum dataset admission gate
No farm/customer data may be posted to public GitHub. Private permission, purpose limitation, veterinary/animal-welfare review where relevant, scale calibration, exact time boundaries, at least one documented flock-cycle and signed data dictionary are prerequisites. Publish no numeric effect, benchmark, causal attribution or economic saving without the raw authorized records and a prespecified comparison. For a retrospective descriptive study, identify selection bias, farm clustering, strain/feed changes and seasonality.

## Reader-usable output of this file
A reviewer can apply the dictionary and conservation equations to an actual authorized flock ledger to decide **admit / quarantine / not estimable** without manufacturing results. Next: R-01 verify data availability and source rights privately, then perform a targeted novelty review before considering any analysis. Earlier AGR-FUT-001–003 and MR/AE/ZM remain queued.

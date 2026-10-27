# MR-2026-001 — prospective event-linkage validation protocol and data dictionary

**Prepared 27 October 2026; internal methods design, not an executed trial, validation study, ethics approval, preregistration, field dataset or result.** This protocol is intended to convert the existing unvalidated G/D/R/A reporting worksheet into a falsifiable study design if independent field data and approvals become available. It does not retroactively change the original eight-study purposive Perspective.

## Research questions and distinct estimands
1. Among eligible generated recommendations, what fraction has a documented successful delivery? `D/G`.
2. Among eligible generated recommendations, what fraction has independently documented receipt? `R/G`; and what fraction has a physically verifiable irrigation action temporally and spatially linked to advice? `A/G`. These are **documentation rates**, not automatically causal effects of DSS.
3. Among **linked recommendation–action pairs**, how often are time and depth within *prespecified, agronomically justified* tolerances? Report the paired denominator and the proportion of adaptations separately; do not relabel adaptation as nonadherence by default.
4. Does a randomized or defensible comparison identify a change in **calibrated water volume per area** or yield-adjusted water productivity? This is a **different causal estimand** from D/G, R/G, A/G.

## Required independent, minimally sufficient event data
| Table | Required key and columns | Source and quality gate |
| --- | --- | --- |
| plot_registry | `plot_id`, crop, area_ha, irrigation method, farm_id, treatment assignment, season dates | Farm consent; immutable plot identifiers; assignment at randomized unit |
| advice_event | `advice_id`, `plot_id`, issued_at_utc, recommended_start_utc, latest_start_utc, recommended_depth_mm, validity_end_utc, supersedes_advice_id, algorithm_version | Original immutable DSS log; timezone conversion documented |
| delivery_event | `delivery_id`, `advice_id`, channel, sent_at_utc, provider_receipt_at_utc, delivery_status | Provider acknowledgement, not merely a software send call |
| receipt_event | `receipt_id`, `advice_id`, accessed_at_utc, evidence_type, verified_by | Receipt/interpretation evidence classified as self-report or independent |
| irrigation_event | `action_id`, `plot_id`, start_utc, end_utc, meter_id, volume_m3, depth_mm, calibration_id, operator_adjustment_reason | Independent meter/logger, calibration certificate and plot-area conversion |
| measurement | `measurement_id`, `plot_id`, at_utc, variable, unit, value, instrument_id, calibration_id, blinded_qc_flag | Calibration and missingness checks; yield units harmonized |
| comparison | `assignment_unit_id`, assignment_method, allocation_time, comparator, deviations, attrition, outcome_window | Pre-specified randomization/quasi-experimental assumptions |

All IDs are pseudonymous. No personal names, exact private farm locations, secrets or unlicensed records should enter the public GitHub branch. The tables above are **schemas only; no rows were generated**.

## Matching algorithm (to be frozen before observing outcomes)
1. Restrict G to unique, applicable, non-test recommendations issued during each prespecified plot-season window; report withdrawn and superseded advice separately, never silently deleting it.
2. D requires a provider-confirmed successful transmission for that exact advice_id; R requires receipt evidence for the same advice_id. A requires a **physically logged action** and a predeclared linkage rule; action alone does not prove receipt.
3. Candidate matches must have the same plot_id and fall in the advice validity interval; preserve all candidates. For one-to-many or many-to-one cases, flag ambiguity and do **not** force arbitrary greedy matching. Primary A numerator includes only unambiguous prespecified matches; report upper sensitivity bound counting all ambiguous cases as potentially matched.
4. Record timing deviation in hours, depth deviation in mm and volume deviation in m³ **separately**. A matching event is not necessarily a compliant event. Distinguish partial adherence, adaptation, equipment limitation, rainfall cancellation and no event.
5. Define denominator exclusions *before* analysis: out-of-season, invalid plot, confirmed duplicated advice, withdrawn before delivery, or genuine meter downtime. Provide flow counts for all exclusions and missing data.
6. Reconcile measured depth by `depth_mm = volume_m3 / (area_ha * 10)` (1 mm on 1 ha = 10 m³). Require instrument calibration; do not infer independent measurement from farmer diary entries.

## Validation and causal identification gates
- **Construct validity:** independent domain experts review each link, evidence category and exclusion rule; blinded dual coders classify a random audit subset. Report raw agreement and Cohen's kappa only if real coder labels exist; no invented reliability coefficients.
- **Linkage accuracy:** independently adjudicate a sample of true and false event matches using raw timestamped logs; report sensitivity, precision, ambiguous fraction and missingness by treatment arm.
- **Cluster structure:** randomize at the unit where advice can spill over (farm, shared canal or irrigation district), not blindly at plot level; document interference, clustering and allocation concealment. No sample-size or detectable effect is claimed before baseline variance and intracluster correlation are available.
- **Primary physical outcome:** metered irrigation volume per irrigated hectare over a prespecified season; yield-adjusted water productivity as secondary with actual yield measurements. Report intention-to-treat separately from per-protocol adherence; use appropriate cluster uncertainty and pre-specified covariates.
- **Failure/stop rules:** do not claim validated G/D/R/A, causal water savings, improved yield or persistent adoption until source integrity, ethics/consent, credible counterfactual and independent adjudication pass.

## Current state
No event-linked field dataset, verified experimental unit, ethics determination, independently calibrated meter log, blinded coder labels or prospective validation results were obtained in this work. This is a **reproducibility-ready design artifact**, not a completed empirical study. **MR remains MAJOR REVISION / NO SUBMISSION.** The human author must review scientific contribution and any final publication decisions.

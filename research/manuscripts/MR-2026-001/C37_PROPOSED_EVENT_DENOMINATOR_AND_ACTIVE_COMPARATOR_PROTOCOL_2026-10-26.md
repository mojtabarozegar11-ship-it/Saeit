# MR-2026-001 C37 — falsifiable recommendation-event denominator and provenance protocol
**Date:** 26 October 2026. **Status:** PROPOSED, NOT VALIDATED; no farm-level observations or assessor trial have been performed. This protocol supports an irrigation-specific Perspective and is **not** a new general theory of fidelity.

## Unit of observation and linkage keys
One record represents **one plot-specific, time-stamped, actionable irrigation recommendation** (the index event), with a stable `recommendation_id`, `plot_id`, `crop_id`, `issue_time_utc`, `advice_valid_from/to`, `advice_version`, `recommended_depth_mm`, and `eligible_for_implementation`. Store `source_uri`, `source_record_id`, `observation_method`, `observer_role`, `timestamp_utc`, `quality_flag` for every claimed downstream event.

Delivery (`sent_at`, channel, gateway acknowledgment), receipt (`receipt_at`, user acknowledgment), and action (`action_id`, measured depth and unit, start/end, method, meter calibration, uncertainty) are separate child records. A receipt log is not proof of comprehension; a survey response is not proof of metered irrigation. Link `action_id` to one or more recommendations only under an **explicit predeclared matching rule**; allow a recommendation to be superseded and an action to address multiple recommendations without double-counting. Do not fabricate linkage where timestamps or plot IDs are missing.

## Explicit denominators and missingness
Let `G` be the number of **distinct applicable recommendations generated** during a prespecified window, excluding superseded/test/not-yet-actionable messages under documented rules. Let `D` be those with evidence of successful delivery; `R` those with evidence of receipt, using a **declared receipt method**; and `A` those with an independently verifiable action matched within a prespecified temporal tolerance. Report:
- `delivery_documented / G` — operational delivery coverage, not adoption.
- `receipt_documented / G` and, separately, `receipt_documented / D` — receipt-documentation fractions, **not necessarily true receipt probabilities**.
- `action_verified / G` — fraction of generated applicable recommendations with an independently documented, appropriately matched action; **not** proof of compliance with prescribed dose or of causal savings.
- `action_verified / receipt_documented` only on a **jointly linkable subset** of recommendations for which both receipt and action status are ascertained. Do not treat unobserved receipt as a negative; do not assume that the numerator is a subset of receipt-documented events without confirming the join.

For every numerator/denominator, include number missing, reason missing, plot count, farm count, observation window, and whether the unit is messages, plots, people, days, irrigation events or volume. Do not equate `45/72` all-season SMS response participation with event-level implementation. Report ambiguous many-to-many matches separately rather than inflating action rates.

## Four separate operational concordance estimands (Baroni 2019 comparator refinement)

The original Wiley abstract of Baroni et al. (2019; DOI 10.1002/ird.2337) reports five of six scheduling methods agreeing on *seasonal irrigation volume* while disagreeing more on irrigation **season and event counts**; users rarely implemented recommendations. Accordingly, the following **four distinct proposed measures** must not be collapsed into a single compliance percentage:

1. **Seasonal total-volume concordance:** for plot `p` and a fully specified season `T`, separately report `sum(observed_metered_m3) / sum(recommended_m3)` and its absolute difference, *only when both totals cover the same plot area, observation window, weather/crop assumptions and irrigation opportunity set*. Convert depths in mm to volumes using measured plot area; record metering uncertainty, omitted events and whether the advice itself changed. An estimated water requirement is not an observed delivered volume.
2. **Event-count concordance:** report the number of distinct observed irrigation starts, number of actionable recommended events, and the matching algorithm's counts of one-to-one, one-to-many, many-to-one and unmatched events. Do not define `observed_event_count / recommendation_count` as a fraction of farmers who complied; a recommendation can legitimately be split or combined.
3. **Event-timing concordance:** among uniquely or explicitly weighted matched event pairs only, report signed lag `actual_start_utc - advice_target_utc`, the prespecified allowed window, median absolute lag and percentage matched within tolerance, with the number of eligible/matched/ambiguous events. A receipt timestamp is not an irrigation start.
4. **Dose concordance:** among verifiably matched actions, report `measured_depth_mm - recommended_depth_mm` and absolute/relative deviation with calibrated measurement error and missingness; do not infer correct dose from mere event occurrence or a survey answer.

**Do not pool these metrics into one unvalidated adherence score.** Every denominator is plot-, event- and window-specific, and missing observation, explicit non-implementation, justified adaptation and device failure are distinct states. The original source does not supply the raw linked events to calculate these metrics; they are falsifiable definitions for a **future validation study**, not new observed findings or priority claims.

## Evidence and causal boundaries
- `M`: physical water/soil/yield measurement with instrument, calibration, units and uncertainty.
- `O`: independently verifiable, recommendation-linked action with an auditable record.
- `S`: self-report, interview, platform engagement or participant diary.
- `P`: modelled or hypothetical result.
- `U`: unavailable/unclear provenance, source access, unit or denominator.
These are **non-ordinal, non-exclusive labels**, not a validated score. An M-labelled plot water-use contrast is not necessarily an O-labelled farmer decision, and neither by itself identifies a counterfactual causal effect. Report adaptation to local constraints as a separate category; non-observation is not farmer refusal.

## Proposed active-comparator validation (future study; not conducted)
Preregister the claim sampling frame, eligible primary papers, source-access levels and blinded adjudication manual. Randomly allocate independent assessors, balancing paper and assessor effects, to:
- **Comparator:** existing TIDieR and Carroll fidelity-informed source extraction, including standard source citation and limitation fields.
- **Increment:** the **same** extraction form plus event key, explicit generated/delivered/received/action denominator fields, observation method and source-to-claim join rule.

The prespecified **primary endpoint** is the proportion of extracted claims adjudicated as containing unsupported inference. Secondary endpoints: inter-assessor agreement, unresolved denominator frequency, false confidence in causal attribution, extraction time and assessor burden. Analyze source/assessor clustering; decide a sample size after pilot variance estimation, not by inventing participants or effect sizes. Preregister handling of ambiguous source texts and negative/null outcomes. Without a completed, adequately powered study this protocol is **a proposed reporting discipline**, not validated methodological innovation.

## Prior-art boundaries
TIDieR: Hoffmann et al. (2014), DOI 10.1136/bmj.g1687; Carroll et al. (2007), DOI 10.1186/1748-5908-2-40; Darouich et al. (2024), DOI 10.3390/agronomy14010066; Tapsuwan et al. (2015), DOI 10.1002/ird.1887; Lagasio et al. (2025), DOI 10.3390/rs17111855. Earlier work already studied recommendation versus practice, fidelity and end-user feedback. The potential increment is **only** transparent source-linked event-denominator accounting; novelty and usefulness remain unproven.

## Release gate
No invented events, respondents, field measurements, inter-rater reliability, human author declarations or journal acceptance. This is an internal methods specification accompanying a manuscript under **MAJOR REVISION**, not an experimental result, journal submission or approved checklist.

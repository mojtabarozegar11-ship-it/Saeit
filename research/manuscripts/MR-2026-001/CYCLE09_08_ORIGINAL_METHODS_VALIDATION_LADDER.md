# MR-2026-001 | Cycle 09 | Original manuscript-ready prospective Methods: Validation ladder
**Status: PROPOSED manuscript language, not executed review results.** Author scientific review and protocol freeze pending.

## A construct-validity ladder for irrigation decision support
The review will classify each empirical claim by the link in the decision-to-outcome pathway it directly observes. **L0 (data acquisition)** comprises farm sensor, weather, soil, and image measurements. **L1 (algorithmic validity)** assesses how accurately a model predicts a target, including whether its labels are independent field measurements, proxy thresholds, or outputs of another model. **L2 (actionable recommendation)** requires a dated irrigation timing, volume, frequency, or allocation recommendation delivered to an identifiable decision maker. **L3 (behavioral implementation)** requires an observable decision, including adherence or documented non-adherence and its denominator. **L4 (farm outcome)** requires a field outcome (applied irrigation volume, crop yield, energy or cost) measured with an identifiable instrument, time window and comparator. **L5 (sustained adoption)** requires evidence of voluntary use beyond study supervision, with the duration and number of eligible farms stated. A study can contribute evidence at several levels; its highest level must not be assigned to all reported outcomes.

At the outcome level, evidence provenance will be coded independently as directly measured (M), observed human behavior (O), respondent-reported (S), modelled or counterfactual (P), or uncertain (U). Thus, high classifier accuracy at L1 cannot be substituted for a reduction in water applied at L4, and a farmer's stated satisfaction at L2 cannot be counted as continued adoption at L5. A field-installed sensor at L0 may be technically mature while adoption outcomes remain unmeasured. For each claim we will retain the source location, outcome definition, farm/season denominator, unit, comparator, uncertainty, and the original authors' limitations.

**External transportability** will be charted separately: within-farm random split, within-site temporal holdout, independent farm, independent region, and multi-season deployment. Where image observations are autocorrelated by tree, farm or day, image-level train/test splitting may overstate field generalization. We will not infer leakage without access to split identifiers; instead, record split unit and mark it unreported if absent. No universal ordinal quality score or pooled percentage saving is presumed.

## Boundary calibration (not screened findings)
- Okayama et al. 2025, DOI 10.1007/s10661-024-13602-1: measured orchard inputs (L0), CNN label prediction (L1), cross-district accuracy drop; no confirmed L3/L4/L5 outcome from the reviewed sections.
- Medina et al. 2024, DOI 10.1038/s41598-024-82344-4: operating farm prototype and weather measurements (L0), potential advisory support, but no confirmed treatment-attributable water saving or sustained uptake.

## Safeguards
Eligibility decisions will be made against a frozen PCC protocol after licensed search exports and actual human screening. This ladder is an extraction framework and must not be used to retroactively exclude negative or null results. PRISMA-ScR flow numbers remain unknown. AI support is not a second human reviewer.

References: Tricco et al. (2018), DOI 10.7326/M18-0850; Okayama et al. (2025), DOI 10.1007/s10661-024-13602-1; Medina et al. (2024), DOI 10.1038/s41598-024-82344-4.

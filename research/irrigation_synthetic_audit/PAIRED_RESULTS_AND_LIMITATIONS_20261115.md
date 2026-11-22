# R01 — paired results and interpretation, native workbook source
**Date:** 2026-11-15 | **Classification:** Internal author-review supplement only.
**Design:** deterministic / synthetic weather and irrigation-policy scenarios.
**No field measurement, randomized field trial, realized crop yield or money outcome.**
This is a reproducible descriptive comparison of archived model outputs.

## Provenance and level of evidence

Primary author-controlled workbook: [ZM-IRR-MODEL-2026-01](https://docs.google.com/spreadsheets/d/1NC1pgdb1Dkhk1HdgdF_sFvnx1i86O88u_fgVdxvvKQA/edit), native tabs
`CohortC1620`, `RegimeR2160`, and `DecisionWeights`, directly read on
2026-11-15. C comprises 1,620 rows (540 matched keys × 3 policies);
R1 comprises 2,160 rows (540 matched keys × 4 policies). They are
**separate** synthetic scenario families, not pooled randomized cohorts.
Each family has twelve modeled climate paths, four dry/four medium/four wet,
with 45 within-path bias × ET multiplier × rainfall-information settings.
No 540-key farm-level independent-sampling claim is defensible.

The outcome source is the native workbook; the Python PR #1999
`paired_scenario_audit.py` is an archive postprocessor. The preceding
independent read-only recomputation confirmed the means, Pareto categories,
and **all 64** entries (eight weights × four measures × two families) from
`DecisionWeights!H1:P9`. This is an arithmetic consistency check, *not*
a replay of independently generated weather or a prospective field test.

## Outcome definitions and signs

For each fixed scenario key, with v2 and v3 evaluated on the same generated
inputs, `ΔV = V_v3 − V_v2` (gross modeled irrigation, m³) and
`ΔQ = Q_v3 − Q_v2` (simulated plot-days with end-of-day storage below
100 mm). Positive ΔV means **v3 applies more modeled water**; negative ΔQ
means **fewer modeled threshold plot-days**. Q is a threshold proxy, not
an observed crop yield, physiological stress diagnosis, or revenue.
The 0.1 ha profile convention and 30-day horizon belong to the original
synthetic simulator assumptions, not a real farm validation.

### Table 1. All matched scenarios, v3 minus v2

| Measure | Cohort C | Regime R1 |
| --- | ---: | ---: |
| Archived policy rows | 1,620 | 2,160 |
| Unique paired keys, v2/v3 | 540 | 540 |
| Modeled climate paths | 12 | 12 |
| Mean paired ΔV (m³) | +36.068955967 | +30.575281425 |
| Median paired ΔV (m³) | +22.837126604 | +22.698814030 |
| Mean paired ΔQ (threshold plot-days) | −6.892592593 | −7.470370370 |
| v3 Pareto-dominates v2 | 65 | 43 |
| v2 Pareto-dominates v3 | 229 | 232 |
| Both water/Q tied | 89 | 94 |
| v3 lower Q but higher water | 157 | 171 |
| v3 lower water but higher Q | 0 | 0 |
| Exhaustive partition total | 540 | 540 |

These values are **descriptive means/medians of simulated paired cases**.
They are not estimates of the real-world average farm treatment effect,
nor evidence that irrigation water is saved. Indeed mean ΔV is positive
in both families, implying more simulated water under v3 than v2 on average.

### Table 2. Climate-class descriptive heterogeneity (180 matched keys per class)

| Family | Climate class | Climate paths | Mean ΔV (m³) | Mean ΔQ (proxy plot-days) |
| --- | --- | ---: | ---: | ---: |
| C | dry | 4 | +9.406963089 | −10.033333333 |
| C | medium | 4 | +39.446877806 | −8.422222222 |
| C | wet | 4 | +59.353027007 | −2.222222222 |
| R1 | dry | 4 | +24.400005637 | −9.155555556 |
| R1 | medium | 4 | +37.204986037 | −9.605555556 |
| R1 | wet | 4 | +30.120852600 | −3.650000000 |

*No p-values or confidence intervals.* The 180 factorial cases in each
row reuse just four synthetic climate paths; naive standard errors based
on 180 independent replicates would be pseudoreplication. Path-level
heterogeneity must be shown; any inferential procedure requires a
separately justified sampling model and cautious small-cluster analysis.

### Table 3. Eight illustrative policy-loss weights, native-sheet crosscheck

`ΔL(λ) = ΔV + λΔQ` where λ has physical proxy units **m³ per threshold
plot-day**; it is not a crop price, pumping tariff, profit, or validated
willingness-to-pay amount. Lower loss is labeled favored, with
`10⁻⁸` tolerance for numerical ties.

| λ | C: v3/v2/tie | C mean ΔL | R1: v3/v2/tie | R1 mean ΔL |
| ---: | --- | ---: | --- | ---: |
| 0 | 20/383/137 | +36.068955967 | 13/401/126 | +30.575281425 |
| 1 | 117/334/89 | +29.176363375 | 115/331/94 | +23.104911054 |
| 2 | 136/315/89 | +22.283770782 | 144/302/94 | +15.634540684 |
| 5 | 161/290/89 | +1.605993004 | 185/261/94 | −6.776570427 |
| 10 | 196/255/89 | −32.856969959 | 193/253/94 | −44.128422279 |
| 20 | 213/238/89 | −101.782895885 | 204/242/94 | −118.832125983 |
| 50 | 217/234/89 | −308.560673662 | 214/232/94 | −342.943237094 |
| 100 | 222/229/89 | −653.190303292 | 214/232/94 | −716.461755612 |

Weights are examined post hoc; no weight constitutes an externally
elicited utility function. Changes in favored policies are model-internal
tradeoffs, not sales recommendations.

## Information availability and model validity

The original archived generator's forecast cases use *modeled realized
same-day rainfall* in at least some hypothetical decision rules. The
`perfect` case must be labeled an **oracle / perfect-information**
scenario; a real farmer cannot assume knowledge of future realized rain
without documented forecast issue-time information. Neither the
weather generator nor this output postprocessor establishes validity of
prospective forecasts, soil calibration, root-zone stress response,
irrigation uniformity, energy costs, revenue, or field yield.

A technically valid reanalysis would record, for every irrigation decision,
the information observable *before* that action, hold ex-ante inputs
identical across policies, and compare both policies under identical
water/application constraints. Preserve the original outputs as a
historical synthetic archive; version any new prospective experiment.

## Relevant peer-reviewed/agency methodology (verified publication details)

1. Allen, R. G., Pereira, L. S., Raes, D., and Smith, M. (1998).
   *Crop Evapotranspiration: Guidelines for Computing Crop Water
   Requirements*. FAO Irrigation and Drainage Paper 56. FAO, Rome.
   [Original agency document](https://www.fao.org/4/X0490E/x0490e00.htm).
   Applicable as a reference for ETo and crop-water methods, **not** as
   an external validation of the present synthetic controller.
2. Cameron, A. C. and Miller, D. L. (2015).
   *A Practitioner's Guide to Cluster-Robust Inference*.
   *Journal of Human Resources* 50(2):317–372.
   [DOI:10.3368/jhr.50.2.317](https://doi.org/10.3368/jhr.50.2.317).
   Appropriate context for dependence and few clusters; no cluster
   sampling inference has been performed for this archive.

## Author / journal / commercial gates (all still open)

- Confirm original output provenance, model-generated data and rights.
- Replay C/R original generator against frozen authenticated CSV/TSV
  source snapshots; preserve SHA-256 of actual source bytes.
- Resolve decision-time rainfall information, pre-specified comparator
  rules, and any hindsight leakage before making prospective claims.
- Validate weather, water balance and crop response with dated independent
  data if real-world agronomic efficacy is claimed.
- Provide full scientific citation verification, byline/author approvals,
  AI assistance disclosure, limitations and journal-specific requirements.
- Verify site-specific delivery, support and permitted licensing before
  marketing any agricultural analysis service. **No external release
  or journal submission is authorized by this internal note.**

## Additional paired simulated outcomes and climate-path deletion sensitivity (15 November update)

These values were recomputed **read-only** from all 1,620 rows of native
`CohortC1620!A1:L1621` and all 2,160 rows of native
`RegimeR2160!A1:L2161` in the author-held
[ZM-IRR-MODEL-2026-01 workbook](https://docs.google.com/spreadsheets/d/1NC1pgdb1Dkhk1HdgdF_sFvnx1i86O88u_fgVdxvvKQA/edit).
The same 540 unique synthetic matched keys per family were paired by
cohort, seed, climate class, bias, ET multiplier and rainfall-information case.
These are descriptive **model outputs**, not independent observed trials,
and no real farm/yield/water savings or financial valuation is inferred.

### Table 4. Additional outcomes: v3 minus v2

| Modeled outcome and unit | Cohort C mean | R1 mean | C paired median | R1 paired median |
| --- | ---: | ---: | ---: | ---: |
| Below-98 end-storage count (synthetic plot-days) | −4.342593 | −4.794444 | 0 | 0 |
| Irrigation events (count across modeled plots) | +1.855556 | +1.703704 | 2 | 1 |
| Drainage sum (mm of modeled summed depth) | +13.435478 | +12.016956 | +0.347607 | +2.145296 |

The `drainage_sum_mm` values are **summed millimetre depths as recorded
by the simulator**; they are not directly volumes in m³. Converting any
individual depth to a volume needs the exact associated plot area and
aggregation semantics. Do **not** attach crop yield, profit or observed
benefit labels to Q98.

### Table 5. Heterogeneity in the three supplementary outcomes

| Family | Climate class | Matched keys | Δbelow-98 days | Δevents | Δdrainage sum (mm) |
| --- | --- | ---: | ---: | ---: | ---: |
| C | dry | 180 | −6.638889 | +0.938889 | +2.965777 |
| C | medium | 180 | −5.194444 | +2.072222 | +11.509785 |
| C | wet | 180 | −1.194444 | +2.555556 | +25.830873 |
| R1 | dry | 180 | −5.927778 | +1.627778 | +5.945195 |
| R1 | medium | 180 | −6.077778 | +2.133333 | +13.279381 |
| R1 | wet | 180 | −2.377778 | +1.350000 | +16.826293 |

Path-cluster nonindependence remains material: each 180-key climate class
has only four weather paths, each repeated under 45 designed settings.
These are *within-model conditional averages*, not environmental population
estimates or confidence intervals.

### Table 6. Delete-one-climate-path deterministic sensitivity

Each of 12 checks in a family removes all **45** keys belonging to a
single simulated climate path and recomputes the paired average on the
remaining **495** keys. The ranges below give the minimum and maximum
of these 12 leave-one-path-out descriptive averages, **not a
bootstrap confidence interval**.

| Family | Number of deletions | Remaining keys per deletion | Range of mean Δwater (m³) | Range of mean ΔQ100 (plot-days) |
| --- | ---: | ---: | ---: | ---: |
| C | 12 | 495 | +31.990085 to +39.347952 | −7.519192 to −6.256566 |
| R1 | 12 | 495 | +27.312080 to +33.354852 | −8.149495 to −7.040404 |

**Observation:** all 24 path-deletion checks retain a positive *modeled*
mean difference in gross water and a negative difference in *modeled* Q.
No sign reversal in this limited check should be misrepresented as a
confidence probability or as external robustness. Unknown model bias,
the retrospective rainfall information set, and absence of real farm
measurements are unaffected by deletion stability.

### Computational contract

The research postprocessor now emits `supplementary_paired_outcomes`
for Q98, irrigation events and drainage (mean, median, range, per-climate
and per-path values) and `leave_one_climate_path_out` for twelve
path-exclusion descriptive comparisons per family. A set of 26 targeted
regression methods was authored for sign, units, paired denominators,
stratification, perturbed paths, medians, and exclusion effects.
Do not describe authored tests as *passing* until CI records for the
corresponding SHA have been checked. The original synthetic generator
still requires source replay and information-time fairness audit.

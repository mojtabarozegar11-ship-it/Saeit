# R01 — Twenty-part scientific methods and claims-control appendix
Date: 2026-11-15. **Internal technical supplement only; all outcomes synthetic, no field observations.** This appendix specifies an auditable analysis plan; it is not a completed statistical analysis or journal-ready manuscript.

## Scope and independent scientific components

1. **Research question.** Compare modeled irrigation volume and modeled Q100 threshold-days between v3 and v2 *within identical synthetic scenario keys*. Do not generalize to farms.
2. **Design.** Two separate simulated families, C (three policies) and R1 (four), with 540 complete scenario keys each. Family is not a randomized treatment arm.
3. **Analysis unit.** One scenario key comprises climate path, seed, class, bias, ET factor and rainfall-information case. Policy rows within each key are paired.
4. **Dependence.** Each family has twelve climate paths; 45 factorial conditions per path. Treating 540 keys as independent replicates would be pseudoreplication.
5. **Primary outcome.** Gross modeled irrigation water V in cubic metres. State simulation horizon and land-area convention before interpreting any total.
6. **Secondary outcome.** Q100 is a simulated threshold plot-day count; neither actual crop yield nor validated physiological stress.
7. **Other outcome.** Drainage is depth (mm), not volume; conversion to m³ requires the corresponding area and explicit assumptions.
8. **Contrast direction.** For each key i, dV_i=V(v3,i)-V(v2,i) and dQ_i=Q(v3,i)-Q(v2,i). Negative dV means modeled v3 uses less water; negative dQ means fewer modeled threshold-days.
9. **Descriptive estimator.** Mean paired difference is sum(d_i)/540 for each family. Also report median, range, and path-specific means; never label this a field causal effect.
10. **Stratification.** Report twelve path-level paired summaries and dry/medium/wet group summaries (four paths each), keeping the original path identities.
11. **Sensitivity grid.** Display all five soil-bias levels × three ET factors × three forecast cases. Their 45 cells are designed conditions, not 45 sampled farms.
12. **Information fairness.** The recovered original generator uses realized modeled rainfall in some perfect/false-positive cases. Separate these oracle-information scenarios from any ex-ante implementable policy comparison.
13. **Pareto partition.** Report five mutually exclusive water/Q categories with tie tolerance and a check that counts sum to 540. Declare how exact ties and floating-point tolerance are defined.
14. **Tradeoff loss.** For each illustrative lambda, dL=dV+lambda*dQ. Lambda has m³ per simulated Q-day units and is **not** a market price or profit.
15. **Decision-weight selection.** Report the entire eight-weight grid, not only the most favorable weight. A post hoc optimal lambda cannot be used as a pre-specified confirmatory hypothesis.
16. **Crossover.** A finite crossover exists only where dQ differs from zero; report missing crossover as null, and specify treatment of negative thresholds.
17. **Uncertainty.** Any future interval should resample climate paths as clusters, preserve all 45 within-path factorial settings, disclose only 12 clusters and perform a small-cluster sensitivity analysis. No confidence interval is claimed here.
18. **Reproducibility.** Freeze original CSV bytes and SHA-256, exact code commit, Python version, invocation, policy mapping, output JSON and full stdout/exit status. Native Sheets arithmetic agreement does not replace generator replay.
19. **External validity.** Require independently collected irrigation meter readings, meteorological forecasts issued before decisions, soil calibration, crop outcomes and a predeclared sampling design before real-world performance claims.
20. **Commercial/editorial gate.** No field water-saving, yield, profitability, controller superiority, publication or customer efficacy claim is authorized by synthetic consistency checks. Author approval, disclosure, methodological review, data rights, and owner-specific submission approval remain open.

## Manuscript-ready wording with bounded claims

**Methods (simulation only).** “We performed a retrospective paired comparison of two controller variants using two author-controlled synthetic scenario archives. Each archive contains 540 matched scenario keys arranged as twelve modeled climate paths with 45 factorial conditions per path. The Cohort C archive contains 1,620 policy outputs and Regime R1 contains 2,160 policy outputs. Outcomes are modeled gross irrigation volume (m³) and a simulated Q100 threshold-day proxy. We calculated within-key v3-minus-v2 differences and descriptive summaries. The archives do not constitute independent field trials.”

**Limitations.** “The weather, soil and controller outputs are simulated. Some information cases use realized modeled rainfall at decision time and therefore represent oracle-information comparisons, not operational forecasts. Repeated factorial conditions within twelve climate paths preclude treating 540 matched keys as independent farm observations. The present postprocessing does not demonstrate yield, financial benefit, real-world water savings or causal effects.”

## Audit table template (not measured results)

| Family | Keys | Paths | Rows | Mean ΔV m³ | Mean ΔQ simulated days | Field validated |
|---|---:|---:|---:|---|---|---|
| C | 540 | 12 | 1,620 | See frozen source crosswalk | See frozen source crosswalk | No |
| R1 | 540 | 12 | 2,160 | See frozen source crosswalk | See frozen source crosswalk | No |

Source provenance, previously verified numerical workbook checkpoints and external FAO-56 / Cameron–Miller bibliography are documented in `SOURCE_CROSSWALK_20261115.md`. This appendix adds **20 defined methodological controls**, not 20 executed experiments, new observations, or passing tests.

**Release:** Internal PR only. No email, journal submission, paid action, merge, or production publication.

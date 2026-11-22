# R01: decision-time identifiability and climate-path inference gate (2026-11-16)

**Status:** author-review scientific supplement, not field evidence or publication clearance. This protocol uses the documented 1,620 Cohort C and 2,160 Regime R1 *simulated* policy rows. The 540 paired keys per family arise from 12 climate paths × 5 sensor biases × 3 ET factors × 3 rainfall-information cases. Policies share keys within a family; keys are not independent farms. The archived outputs cannot establish real-world water savings, yield, or profit.

## Estimands and unit of inference

For each family F ∈ {C,R1}, path p=1..12 and factorial setting j=1..45, define d(F,p,j)=Y(v3,F,p,j)−Y(v2,F,p,j). Compute path mean D(F,p)=sum_j d/45, and the finite-grid descriptive mean Dbar(F)=sum_p D/12. For a fixed archive, Dbar is a descriptive finite-grid contrast; it is **not** a population causal effect. Report each outcome separately, with its units and sign convention. Never pool C and R1 without declaring weights and scientific rationale.

For uncertainty about *independently sampled climate paths*, report path-level distribution and (only if exchangeability and sampling mechanism are justified) a path-cluster bootstrap with 12 resampled path IDs per family and complete within-path 45-key blocks. Clearly label any resulting interval conditional on the simulator and the 12 paths; a bootstrap cannot correct simulator misspecification, future-rainfall leakage or nonrepresentative weather. Do not bootstrap 540 rows as independent farms.

## Decision-time information gate

For every simulated daily decision t, preserve: path ID, seed, policy, scenario, observation timestamp, decision timestamp, forecast issue timestamp, forecast valid time, measured rainfall available by decision time, forecast rainfall available by decision time, realized rainfall, ET forecast issue time, and chosen irrigation action. An ex-ante controller may use only observations with availability time ≤ decision time and forecasts issued ≤ decision time. A 'perfect forecast' policy that reads realized same-day rain before that rain is observable is an **oracle benchmark**, not a deployable controller. Compare policies under identical permissible information sets or label contrasts non-comparable. Without this event trace, **no prospective superiority claim**.

## Reproducibility and water accounting

Freeze exact CSV byte hashes independently of the postprocessor, generator code SHA, configuration, seeds, model version, timezone and unit conventions. Replay the original daily generator/controller and compare outputs with tolerances specified *before* replay. For each day and consistent root-zone control volume, check ΔS=P+I−ET−R−D+L where L represents explicitly documented additional net lateral/capillary terms; report residual and unit mm. Do not equate reduced modeled threshold-day count with lower irrigation withdrawal. More modeled events or drainage may be an adverse tradeoff. Economic evaluation requires observed or separately declared costs, crop response, and a defined price/currency/year; proxy V+λQ is not profit.

## Results table contract (do not fill absent measurements)

| Family | Independent paths | Paired keys | Policy rows | Mean Δ threshold days | Mean Δ irrigation events | Mean Δ drainage (mm) | Field effect |
|---|---:|---:|---:|---:|---:|---:|---|
| C | 12 | 540 | 1,620 | verify against frozen archive | verify | verify | not measured |
| R1 | 12 | 540 | 2,160 | verify against frozen archive | verify | verify | not measured |

These counts describe the existing model design, not independently collected field samples. All numeric outcome cells remain deliberately unfilled until exact frozen-input checks are rerun in this cycle.

## Twenty independent release-evidence gates

1. Author permission and byline confirmed; 2. manuscript version and journal scope pinned; 3. exact source CSV byte hashes independently escrowed; 4. generator source SHA frozen; 5. configuration and RNG seeds archived; 6. daily input weather provenance documented; 7. forecast issue timestamps available; 8. action timestamps available; 9. no future-rainfall oracle leakage in deployable comparison; 10. identical information sets across policies; 11. all 540 paired keys per family complete; 12. all 12 path clusters per family identified; 13. numeric output checkpoints independently recomputed; 14. generator/controller replay matches archive; 15. root-zone balance residuals audited in mm; 16. irrigation volumes/events and drainage tradeoffs disclosed; 17. uncertainty uses path clusters rather than pseudoreplicated rows; 18. field calibration or explicit simulation-only limitation approved; 19. cost and crop response evidence supports any economic claim; 20. rights, AI disclosure, independent scientific review and submission permission documented.

**Gate status for this document:** 0/20 newly verified. Writing a gate is not passing it. Existing prior-cycle evidence must be linked by immutable source SHA and exact CI run before promoting any gate to passed. Overall manuscript readiness percentage is **not estimable** from this checklist.

## Methodological references (not evidence that R01 passed)

- Allen, R.G. et al. (1998), *Crop evapotranspiration: Guidelines for computing crop water requirements*, FAO Irrigation and Drainage Paper 56, https://www.fao.org/4/X0490E/X0490E00.htm
- Hurlbert, S.H. (1984), Pseudoreplication and the design of ecological field experiments, *Ecological Monographs* 54(2), 187–211, https://doi.org/10.2307/1942661
- Cameron, A.C. & Miller, D.L. (2015), A practitioner's guide to cluster-robust inference, *Journal of Human Resources* 50(2), 317–372, https://doi.org/10.3368/jhr.50.2.317

**Release decision:** HOLD — simulation-only; no field efficacy, customer outcome, revenue, submission, merge or deployment asserted.

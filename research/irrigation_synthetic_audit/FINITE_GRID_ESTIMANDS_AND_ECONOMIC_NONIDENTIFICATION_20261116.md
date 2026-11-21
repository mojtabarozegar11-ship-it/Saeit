# R01 — Manuscript-ready finite-grid estimands and economic non-identification (2026-11-16)

**Scope:** A critical correction to interpretation of the existing author's *synthetic* irrigation workbook. This document is not a new field experiment, original generator replay, peer review, or permission to submit/sell. All numbers below are **transcribed from** `LIVE_WORKBOOK_PATH_SENSITIVITY_20261116.md` in this PR, **not independently recalculated in this commit**.

## 1. Explicit estimands and units

For family f ∈ {C,R1}, path p ∈ {1,…,12}, factorial configuration k ∈ {1,…,45}, and outcome Y, define the matched simulated contrast d[f,p,k]=Y[v3,f,p,k]−Y[v2,f,p,k]. The **finite-design estimand** is D[f]=(1/12) Σ_p [(1/45) Σ_k d[f,p,k]]. Equal path and factorial weights are part of this definition; they do not represent surveyed farm weights. The reported C and R1 grids each contain 540 paired configurations, not 540 independently sampled farms. The 12 path means are descriptive units, and independence of paths has not been established. A confidence interval for a farm population, causal field effect, or forecast deployment effect is therefore **not identified**.

The source uses gross applied irrigation volume in m³, Q100/Q98 modeled threshold-days, irrigation-event counts, and drainage **depth** in mm. Do not add a depth in mm to a volume in m³. Do not equate gross applied irrigation with net consumptive crop water use, water withdrawal at a canal, or water depletion at basin scale.

## 2. Numerical correction: v3 is not water-saving

| Synthetic family | Δ gross irrigation m³ (v3−v2) | Δ Q100 modeled days | Δ Q98 modeled days | Δ irrigation events | Δ drainage depth mm |
|---|---:|---:|---:|---:|---:|
| C | +36.068956 | −6.892593 | −4.342593 | +1.855556 | +13.435478 |
| R1 | +30.575281 | −7.470370 | −4.794444 | +1.703704 | +12.016956 |

**Defensible sentence:** “Within the archived simulated factorial grid, policy v3 applied more gross irrigation water and produced fewer modeled low-water threshold-days than v2; this is a model-specific trade-off, not a measured water saving or demonstrated farm benefit.”

**Prohibited sentence:** “v3 saves irrigation water, increases crop yield, or raises farm profit.” None follows from the above grid.

## 3. Economic identification

Let ΔW be alternative-minus-baseline applied water per hectare (m³/ha), ΔE electricity (kWh/ha), ΔC_other other variable costs (currency/ha), ΔF incremental allocated fixed costs (currency/ha), ΔY crop yield (kg/ha), and P crop price (currency/kg). Under **explicitly assumed** linear tariffs pW and pE, the accounting difference is

Δπ = P·ΔY − pW·ΔW − pE·ΔE − ΔC_other − ΔF.

If P>0, break-even incremental yield is ΔY_BE=(pW·ΔW+pE·ΔE+ΔC_other+ΔF)/P. This is a conditional accounting identity, not an estimate of ΔY. The synthetic R01 workbook does **not** identify farm-area normalization of its path-level ΔW, energy, tariffs, realized yield, fixed costs, or crop price. **Do not substitute** the workbook's +36.068956 or +30.575281 m³ into a per-hectare farm budget without verified area and temporal scope. Zero or negative prices require separate defined handling; no arbitrary numerical defaults are justified.

A scalar decision proxy L(λ)=W+λQ100 has a **dimensionful** λ measured in m³ per modeled threshold-day. λ is a decision-maker's hypothetical exchange rate, not a market price, farm profit, or evidence that water can be purchased at that rate. From the finite-grid family means, the algebraic crossover λ* = −ΔW/ΔQ100 is approximately **5.233** for C and **4.093** for R1, in those proxy units. These are derived from rounded descriptive means and are not economically calibrated willingness-to-pay values. The average proxy's sign crossing is distinct from the number of individual factorial configurations favoring v3.

## 4. Twenty distinct evidence gates with falsifiable acceptance criteria

| ID | Gate | Acceptance evidence (none is asserted completed here) |
|---|---|---|
| E01 | Original data identity | Independent frozen source export with byte hash and custody record |
| E02 | Source schema | Exact headers, units, types and dictionary version |
| E03 | Paired key uniqueness | Every family/path/factor/policy key occurs exactly once |
| E04 | Paired completeness | Exactly two policies per 540 family-specific matched keys |
| E05 | Path independence | Documented seed/weather generation and cross-path dependence |
| E06 | Decision-time legality | Forecast issue timestamp no later than each control action |
| E07 | Oracle isolation | Perfect-forecast runs explicitly separated from deployable forecasts |
| E08 | Information parity | v2/v3 compared with the same available-at-decision information |
| E09 | Weather replay | Independent weather generation matches frozen trajectories |
| E10 | Controller replay | Recomputed actions reproduce daily source decisions |
| E11 | Water balance | Daily inputs−outputs−storage change closes within predeclared tolerance |
| E12 | Area/time normalization | Source irrigation m³ reconciled to hectares and season length |
| E13 | Irrigation efficiency | Gross vs net, conveyance and return flows separately specified |
| E14 | Outcome definitions | Q100/Q98 threshold and modeled-day counting fixed before analysis |
| E15 | Missingness | Missing and nonfinite values enumerated, not silently imputed |
| E16 | Sensitivity | Full 24 path means and leave-one-path-out perturbations reproduced |
| E17 | Inference | Sampling frame and cluster exchangeability justified before p-values |
| E18 | Farm economics | Yield, price, energy, water tariff, area and costs sourced independently |
| E19 | External validation | Field design, measurement calibration and external holdout documented |
| E20 | Publication rights | Author sign-off, source rights, disclosures and journal requirements recorded |

A gate is “passed” only with an identified artifact, exact version/hash, reproducible command, expected/observed result, and independent reviewer where appropriate. Writing this table is **zero executed validations**.

## 5. Mandatory manuscript limitations

The workbook contains simulated model outputs and scenario-level arithmetic checks, not empirical observations. The observed model reduction in Q100/Q98 threshold-days is not evidence of improved crop yields or reduced real-world drought losses. Perfect-forecast scenarios may use future realized rainfall; until time-indexed issuance and equal information sets are demonstrated, prospective controller superiority is not identifiable. Climate-path sample size and model design preclude population-wide causal inference. Costs, income, payment acceptance and commercialization cannot be inferred from these outputs.

**Disposition:** DRAFT / NO SUBMISSION / NO SALE / NO MERGE. Next executable step is frozen source replay and decision-time trace verification, not another claim based on the same worksheet.

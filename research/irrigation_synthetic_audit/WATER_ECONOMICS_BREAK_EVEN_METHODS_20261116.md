# R01 — water–economics break-even analysis, non-empirical methods appendix (2026-11-16)

**Status:** Analytical framework only. All outcomes in R01 are simulated; this document introduces no measured costs, observed yields, prices, or field benefits. It does not assert that v3 is superior or marketable.

## Estimand, perspective and unit discipline

For each matched path p and factorial key j, define the modeled difference as v3 minus v2. Keep C and R1 separate. Irrigation application depth I (mm), drainage D (mm), Q98 threshold days (days), and event count N (events) are *different* outcomes. Never substitute Q98 for irrigation water use or drainage for water consumed. A 1 mm depth on a hectare equals 10 m³, **only for a spatially uniform depth over that hectare**; field conveyance efficiency and pumping volume require additional measurements.

For a declared irrigated area A hectares, pumping lift H metres, combined pump/motor efficiency η (0<η≤1), water density ρ kg/m³, gravity g m/s², and electricity price c_e currency/kWh, an illustrative marginal electricity cost for an *additional pumped depth* ΔI_mm is

ΔV_m³ = 10 A ΔI_mm; ΔE_kWh = ρ g H ΔV_m³ / (3.6×10⁶ η); ΔC_energy = c_e ΔE_kWh.

Negative ΔI implies potential pumping savings under unchanged lift and efficiency; do **not** report a negative physical electricity bill. This formula is conditional on pumped water equalling applied water and ignores dynamic head, tariffs, demand charges and network losses. Water procurement price c_w per m³ adds ΔC_water=c_w ΔV. Additional event count ΔN may incur per-event labor/startup cost c_n, but costs are not necessarily linear and should be estimated from observed operations.

For yield change ΔY tonnes/ha and net farmgate margin m currency/tonne, define an explicitly *hypothetical* incremental net margin:

ΔΠ = A m ΔY − (c_w ΔV + c_e ΔE + c_n ΔN + ΔC_maintenance + ΔC_capital + ΔC_risk).

Here ΔC terms are v3 minus v2, with currency, price year, taxes and depreciation specified. **Neither ΔY nor m nor cost parameters is identified by the R01 synthetic archive.** Setting them to zero is a scenario assumption, not a measurement. If A m>0, the break-even yield response is ΔY_BE = (ΔC_total)/(A m), where ΔC_total includes all incremental costs. If A m≤0, do not divide; report break-even undefined. A negative threshold means costs are already lower under assumptions, not proof of higher realized profit.

## Sensitivity grid — inputs to collect, not observed values

| Parameter | Unit | Source needed | Failure condition |
|---|---|---|---|
| A | ha | Verified irrigated plot boundary | A≤0 or unknown |
| ΔI | mm per matched scenario | Frozen simulation archive with explicit water definition | Confused with event count or Q98 |
| H | m | Pumping head measurement | Unknown or nonpositive |
| η | fraction | Pump test or efficiency curve | Outside (0,1] |
| c_e | currency/kWh | Dated tariff and applicable tier | Undated or wrong currency |
| c_w | currency/m³ | Water rights/invoice | No contractual basis |
| ΔN | events | Matched scenario counter | Event semantics differ |
| c_n | currency/event | Audited labor and start costs | Unsupported zero assumption |
| ΔY | tonnes/ha | Independent field yield trial | Modeled Q98 misrepresented as yield |
| m | currency/tonne | Dated market price net of variable harvest/marketing cost | Gross price used as net margin |
| ΔC_maintenance | currency | Equipment logs | Missing cost category |
| ΔC_capital | currency | Amortization schedule and service life | Upfront cost ignored |
| ΔC_risk | currency | Explicit risk valuation method | Arbitrary monetization |

## Reproducibility and falsification

1. Freeze source-file SHA-256 and document whether irrigation represents applied, diverted or pumped depth.
2. Compute ΔI, ΔN, ΔD and ΔQ98 within matched keys, then average **within path** before summarizing across the 12 paths.
3. Preserve all 12 path-specific results and the dry/medium/wet grouping; do not claim 540 independent weather replications.
4. Show signs and units for each difference; test whether a claimed saving is actually a Q98 reduction rather than ΔI<0.
5. Report irrigation-depth and event-count tradeoffs jointly, without selecting only favorable metrics.
6. Obtain pump head and efficiency from independently documented operating conditions; otherwise leave energy outputs uncalculated.
7. Obtain applicable energy tariff, water price and year; do not blend currencies or price years.
8. Separate fixed, per-event and per-volume costs; document nonlinear tariffs and pumping constraints.
9. Estimate yield response from independent agronomic evidence, not from the Q98 proxy.
10. Identify crop, season, soil and spatial domain before attempting transportability.
11. Quantify weather-path uncertainty at the path level, conditional on an explicit path-sampling assumption.
12. Run a sign-reversal sensitivity over plausible input ranges, with ranges attributed to verifiable sources.
13. Include downside scenario with ΔY≤0 and increased event costs.
14. Include drainage/externality accounting separately from private farm profit.
15. Record any foreknowledge of realized rainfall in the decision-time information set; oracle scenarios are not operational policy evidence.
16. Verify water balance and units before interpreting irrigation efficiency.
17. Check paired archive identity and missingness without imputing favorable outcomes.
18. Separate price sensitivity from physical water sensitivity.
19. Require author rights, reproducible generator replay and independent review before submission.
20. Require actual customer contract, lawful claims and independently validated benefit before monetization.

These are **20 specified checks, not 20 completed empirical validations**. A reviewer should mark each with command, input hash, evidence link, reviewer and date. Without those records the completion count is zero.

## References

Allen, R.G. et al. (1998), *Crop evapotranspiration: Guidelines for computing crop water requirements*, FAO Irrigation and Drainage Paper 56, https://www.fao.org/4/X0490E/X0490E00.htm (definitions and crop-water accounting). Cameron, A.C. & Miller, D.L. (2015), *A Practitioner's Guide to Cluster-Robust Inference*, https://doi.org/10.3368/jhr.50.2.317 (dependence and inference). These references **do not** validate any R01 simulated outcome or economic parameter.

**Release gate:** NO journal submission, email, merge, deployment, sale, or claim of realized revenue from this appendix.

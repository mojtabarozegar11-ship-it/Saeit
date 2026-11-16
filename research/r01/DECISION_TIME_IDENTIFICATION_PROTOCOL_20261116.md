# R01 — Decision-time leakage and partial-identification protocol (2026-11-16)

**Status:** Methodological supplement for a *synthetic* irrigation simulation; not field evidence, a completed reanalysis, or publication clearance. No new observations are asserted.

## Estimand and experimental unit
For family f ∈ {C,R1}, climate path p (12 per family), matched scenario key k (45 per path), and policy a ∈ {v2,v3}, define modeled outcomes W(f,p,k,a) (gross irrigation m³), Q(f,p,k,a) (modeled Q98 threshold-days), E(f,p,k,a) (irrigation event count), and D(f,p,k,a) (drainage depth mm). The paired contrast is ΔY(f,p,k)=Y(f,p,k,v3)−Y(f,p,k,v2). Path-level means are δ(f,p)=ΣₖΔY/45; family descriptive mean is Σₚδ/12. Report family results separately; the 540 matched keys per family are **not** 540 independent climatic replicates. The 3,780 archived policy rows are modeled records, not experimental plots.

## Information-set parity (prospective claims gate)
For each decision timestamp t and policy a, construct an immutable information set I(a,t) containing forecast issuance timestamp, forecast valid interval, observed rain available by t, soil-state observation time, and controller version. Define availability(x,t) = [issued_at(x) ≤ t] and [observation_available_at(x) ≤ t]. Every rainfall predictor consumed at t must satisfy availability; realized same-day rainfall known only after t is forbidden unless explicitly a retrospective perfect-information oracle. Both compared policies must have equivalent information access. A failed gate invalidates prospective policy superiority claims, even if outcome arithmetic is correct.

## Two distinct estimands, not interchangeable
1. **Retrospective oracle comparison:** ΔY computed using original archived controllers and information as recorded. Descriptive model comparison only; may incorporate look-ahead.
2. **Prospective fair-information comparison:** re-run *both* policies with the same time-stamped, ex-ante weather information and frozen generator, initial states, seeds and climate paths. This estimand is **not identified** by the existing outcome-only archive if issued-at-time forecast histories are absent. Do not relabel oracle results as prospective results.

## Path-aware uncertainty and robustness
- Report all 12 path-specific δ values per family, median, min/max, and dry/medium/wet strata (four paths per stratum). Do not treat the 45 scenario variants within a path as independent weather realizations.
- Leave-one-path-out estimates δ(-p)=Σ_{q≠p}δ(q)/11 for each of 12 deletions. This is a sensitivity diagnostic, **not** a confidence interval.
- If interval estimation is later justified, resample entire climate paths within each family, preserve within-path matched pairs and declare seed, number of draws and small-cluster limitations. Twelve paths alone do not establish field-population uncertainty.
- Sensitivity to perfect-forecast leakage must be assessed by rerunning with causal forecasts, not by post-hoc subtracting a guessed rainfall bias.

## Economic identification boundary
For ΔW>0 (additional modeled irrigation), incremental private net value per scenario is Δπ=P_yΔY_crop−P_wΔW−C_energy−C_labor−C_capital−C_other, with consistent currency, volume and period units. ΔY_crop and prices are *unobserved* unless independently supplied; consequently neither Δπ nor break-even profitability is empirically estimated from W/Q alone. The conditional crop-yield break-even is ΔY_crop*=(P_wΔW+C_energy+C_labor+C_capital+C_other)/P_y for P_y>0. If ΔW<0, retain the signed term rather than assuming savings from fewer threshold days. Q is a modeled stress proxy, not measured yield.

## Source-to-claim matrix
| Claim | Archive support | Further evidence needed | Allowed language |
|---|---|---|---|
| Policy-row counts and paired scenario arithmetic | Original modeled output, subject to immutable hash/replay | frozen native exports and reproducible checksum | 'archived simulated outcomes' |
| Lower modeled Q threshold-days | Paired model outcomes | code/units/checkpoint replay | 'modeled threshold-day contrast' |
| Lower real-world water use | None | field meters, sampling protocol, calibration | **Not supported** |
| Prospective controller superiority | Not identified when oracle rainfall leaks | issued-at-time forecasts and equal information sets | **Not supported** |
| Yield or profit improvement | None | measured yield and verified costs/prices | **Not supported** |
| Statistical generalization to farms | None | sampling frame, independent sites/seasons | **Not supported** |

## Reproducible release gate
A scientific release requires: immutable source checksums; exact generator commit and deterministic replay; documented matching keys and policy definitions; explicit outcome units; 12 independent path IDs per family; zero missing/duplicate pairs; time-stamped forecast provenance; ex-ante parity; stratified sensitivity; uncertainty statement at path level; economic inputs and rights; author/editorial approval; exact-head CI and independent review. Until these are evidenced, **NO SUBMISSION / NO COMMERCIAL CLAIM**.

### Reference basis (methodological, not a claim of source-data verification)
Allen, Pereira, Raes & Smith (1998), *Crop evapotranspiration*, FAO Irrigation and Drainage Paper 56, https://www.fao.org/4/x0490e/x0490e00.htm . Cameron & Miller (2015), *A Practitioner's Guide to Cluster-Robust Inference*, Journal of Human Resources 50(2), 317–372, https://doi.org/10.3368/jhr.50.2.317 .

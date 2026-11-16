# R01 — pre-specified cluster sensitivity and decision-time audit (2026-11-16)

**Scope:** Methods supplement for simulated Cohort C and Regime R1 only. No field measurements, causal treatment effect, validated profitability or release approval. Complements, does not replace, DECISION_TIME_IDENTIFIABILITY_AND_CLUSTER_PROTOCOL_20261116.md.

## Auditable estimand and uncertainty

Let F denote family (C or R1), p one of 12 simulated climate paths and j one of 45 factorial settings. For an outcome Y with an explicitly declared unit, compute d_{Fpj}=Y(v3)-Y(v2), D_{Fp}=(1/45)Σ_j d_{Fpj}, and Δ_F=(1/12)Σ_p D_{Fp}. The **finite archive Δ_F** is descriptive, not a population estimate. For path-level variability, s_F²=Σ_p(D_{Fp}-Δ_F)²/11 and SE_path=s_F/√12. A t interval Δ_F ± t_{11,0.975} SE_path is an exploratory conditional interval **only if** 12 paths are exchangeable independent draws from a defined weather-generating distribution. Without that premise, report only the twelve path effects, range, and leave-one-path-out influence; do not label any interval a frequentist coverage guarantee.

For each p, Δ_{F,-p}=(Σ_{q≠p}D_{Fq})/11. Define influence I_{Fp}=Δ_F-Δ_{F,-p}; report max |I| and whether the sign of Δ reverses for any deletion. This is sensitivity, **not** cross-validation of agronomic predictions. If climate classes dry/medium/wet are deliberately balanced at 4 paths each, an unweighted mean estimates the design-balanced synthetic mixture, not necessarily the actual regional climate distribution. Any real-world weighted estimate requires independently justified class probabilities w_k summing to one.

## Pre-specified evidence table — blank until independently rerun

| Family | Path IDs verified | ΔQ98 (days) | Δ events (count) | Δ irrigation (mm) | Δ drainage (mm) | max leave-one-path-out influence | Decision-time leakage |
|---|---|---|---|---|---|---|---|
| C | pending immutable source check | pending | pending | pending | pending | pending | unknown |
| R1 | pending immutable source check | pending | pending | pending | pending | pending | unknown |

Prior PR narrative reports modeled mean ΔQ98 C −4.342593 / R1 −4.794444; Δ events C +1.855556 / R1 +1.703704; Δ drainage C +13.435478 mm / R1 +12.016956 mm. **These are previously reported model outputs, not independently recomputed in this supplement.** In particular, no irrigation-withdrawal reduction follows from Q98 improvements.

## Twenty distinct executable audit specifications (NOT passed)

| ID | Scientific control | Required evidence / failure rule |
|---|---|---|
| B01 | Archive provenance | Independent SHA-256 of each original input CSV; reject hash mismatch |
| B02 | Source schema | Original column names, types, units and missingness inventory |
| B03 | Family separation | C and R1 analyses run separately; reject accidental pooling |
| B04 | Paired identity | Exactly one v2 and one v3 per family/path/factorial key |
| B05 | Factorial completeness | 12×5×3×3 unique keys per family |
| B06 | Path identity | Exactly 12 verified seeds/path IDs per family |
| B07 | Class composition | Dry/medium/wet each has 4 distinct paths per family |
| B08 | Finite values | Reject NaN, ±Infinity, impossible sign and unit errors |
| B09 | Q98 definition | Document threshold, duration, temporal aggregation and direction |
| B10 | Event definition | Define event trigger and ensure comparable counts |
| B11 | Irrigation depth | Report withdrawal/application mm separately from event count |
| B12 | Drainage depth | Report summed drainage in mm; never confuse with count |
| B13 | Path-level effects | Produce 12 paired D values per family and outcome |
| B14 | Leave-one-path-out | Produce 12 Δ_-p values and max absolute influence |
| B15 | Cluster uncertainty | Document exchangeability assumption before any t/bootstrap interval |
| B16 | Climate weighting | Disclose design-balanced mixture; require external weights for extrapolation |
| B17 | Forecast issue-time | Each policy forecast issued no later than action decision |
| B18 | Oracle leakage | Flag realized same-day rain unavailable at decision time |
| B19 | Daily water balance | Audit ΔS−(P+I−ET−R−D+L) residual, with L defined and mm units |
| B20 | Economic validity | Reject profit/ROI claims absent costs, crop response, price year and market evidence |

**Implementation acceptance:** B01–B20 each needs a stored input identifier, exact SHA, deterministic command, observed output, reviewer, and pass/fail. Writing these criteria is **0/20 new verified controls**. A successful code CI alone does not validate source data, forecast timing, field calibration, or legal rights.

## Publication and commercialization stop rules

No publication, journal email, sale, efficacy claim, or field recommendation while original generator replay, decision-time event trace, source permissions, model calibration and independent review are unverified. Any 'perfect forecast' use of future realized rainfall must be disclosed as an oracle scenario and excluded from deployable policy superiority claims. No inferred revenue.

**Methods sources:** Allen et al. (1998), FAO-56 https://www.fao.org/4/X0490E/X0490E00.htm ; Hurlbert (1984) https://doi.org/10.2307/1942661 ; Cameron & Miller (2015) https://doi.org/10.3368/jhr.50.2.317 . These support methodology, not R01 empirical validity.

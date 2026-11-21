# R01: reproducibility contract and leakage-safe decision-time audit (2026-11-16)

**Scope:** pre-publication scientific specification for the *synthetic* R01 irrigation study, not observed farm performance. Existing PR #1999 reports C=1,620 policy rows (540 matched keys × 3 policies) and R1=2,160 (540 × 4), with 12 simulated climate paths per family. Those counts are metadata from the PR; this document does not re-read the original author-owned archives. No new measurements or statistical significance are claimed.

## Executable audit contract (20 distinct assertions to implement and evidence)
| ID | Scientific assertion | Exact failure condition / required evidence |
|---|---|---|
| A01 | Archive integrity | SHA-256 manifest absent or digest mismatch |
| A02 | Generator provenance | Source revision, seed and parameter file not pinned |
| A03 | Dataset semantics | Source marks synthetic records as field observations |
| A04 | Stable paired key | Duplicate (family,path,scenario,policy) tuples |
| A05 | Full policy set | C keys not exactly 3 policies; R1 not exactly 4 |
| A06 | Scenario cardinality | Not exactly 540 matched keys per family in frozen source |
| A07 | Climate path cardinality | Not exactly 12 paths per family |
| A08 | Path-class balance | Not exactly 4 dry/4 medium/4 wet paths per family |
| A09 | Independent unit | Inference uses policy-row N as farm-replicate N |
| A10 | Decision timestamp | Controller action lacks decision timestamp |
| A11 | Forecast issue timestamp | Forecast issue time later than action time |
| A12 | Information parity | Policies compared with different permissible information |
| A13 | Realized-rain leakage | Same-day realized rainfall used before it was observable |
| A14 | Unit reconciliation | Applied irrigation, drainage and storage terms mix mm and m³ |
| A15 | Physical mass balance | Inputs minus outputs minus storage change exceeds documented tolerance |
| A16 | Outcome definition | Q98 or quality proxy lacks units, direction and threshold definition |
| A17 | Paired estimand | Policy effect not calculated within identical scenario keys |
| A18 | Cluster sensitivity | Missing all 12 leave-one-path-out descriptive contrasts |
| A19 | Multiplicity disclosure | Eight lambda weights reported as confirmatory without adjustment/pre-registration |
| A20 | Publication rights | Author consent, data rights or disclosure approvals missing |

**Interpretation:** A01–A20 are prospective verification gates, *not* twenty completed empirical checks. A10–A13 are currently critical unresolved fairness gates; a perfect-forecast controller using realized rainfall cannot be described as deployable prospective superiority.

## Estimand and aggregation
For family f, climate path h, matched scenario key k and policy p, let Y(f,h,k,p) be a simulated outcome. Compute paired delta D(f,h,k,p)=Y(f,h,k,p)-Y(f,h,k,baseline). For each path compute the mean across its matched k, then report all 12 path means, their median, minimum, maximum, and dry/medium/wet class summaries. The path is the dependence cluster; no row-wise IID standard errors. Report denominators and missingness explicitly. An exploratory leave-one-path-out analysis removes one whole path at a time and recomputes summaries; it is *not* a confidence interval.

## Data dictionary to complete before claims
| Field | Required unit/definition | Provenance |
|---|---|---|
| applied_irrigation | mm per modeled season, net or gross stated | Source mapping pending |
| drainage | mm per modeled season | Source mapping pending |
| water_withdrawal | m³ per hectare or mm, conversion documented | Source mapping pending |
| Q98 | modeled threshold-day count; threshold and direction specified | PR descriptive claim, definition pending |
| irrigation_events | integer modeled event count | PR descriptive claim |
| yield | measured kg/ha versus simulated proxy explicitly distinguished | No observed field evidence |
| pumping_energy | kWh with head, efficiency and tariff assumptions | No measured energy evidence |
| climate_path | simulated dependence-cluster identifier | PR reports 12 per family |
| forecast_issued_at | timestamp before controller decision | Critical missing provenance |
| decision_at | controller decision timestamp | Critical missing provenance |

## Scientific interpretation and commercial stop
The existing PR describes mean v3-v2 simulated Q98 threshold-day differences of -4.342593 (C) and -4.794444 (R1), but modeled irrigation event differences of +1.855556 and +1.703704 and modeled drainage-depth differences of +13.435478 mm and +12.016956 mm. These are **PR-reported synthetic descriptive values, not independently recomputed here**. The increase in events and drainage is a potential adverse tradeoff; no realized water savings, yield improvement, cost reduction, profit or causal field effect follows. Reproduce from frozen source before citing any numeric value externally.

**Release gate:** require original generator replay, forecast timing and equal information, validated water balance, independent field data for agronomic claims, rights/author approval, scientific peer review, and exact-head CI. Until then: DRAFT / NO JOURNAL SUBMISSION / NO SALES CLAIM / NO DEPLOYMENT. This file changes documentation only; it triggers no host, payment, email, or production operation.

## References to verify against the manuscript
- Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). *Crop evapotranspiration: Guidelines for computing crop water requirements*. FAO Irrigation and Drainage Paper 56. https://www.fao.org/4/x0490e/x0490e00.htm
- Imbens, G.W. and Kolesár, M. (2016). Robust Standard Errors in Small Samples: Some Practical Advice. *Review of Economics and Statistics*, 98(4), 701–712. https://doi.org/10.1162/REST_a_00552

**Next evidence:** attach a reproducible frozen-input digest manifest and a timestamped ex-ante forecast-information matrix; run the A01–A20 checks and archive outputs. No synthetic record may be relabeled as a field measurement.

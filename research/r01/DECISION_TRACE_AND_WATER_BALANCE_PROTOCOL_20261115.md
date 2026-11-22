# R01 — decision-time leakage and water-balance verification protocol (2026-11-15)

**Scope:** executable specification for future audit; no new empirical observations or successful checks are claimed. All archived outcomes in PR #1999 are synthetic. This protocol addresses G13–G15 in the existing evidence matrix; it does not close them.

## 1. Immutable daily trace contract
One row per `family, climate_path, scenario_key, policy, day, decision_id`. Required fields: `decision_at_utc`, `forecast_issued_at_utc`, `forecast_valid_from_utc`, `forecast_valid_to_utc`, `forecast_precip_mm`, `observed_precip_mm`, `observation_available_at_utc`, `irrigation_decision_mm`, `irrigation_applied_mm`, `et_actual_mm`, `runoff_mm`, `drainage_mm`, `soil_storage_before_mm`, `soil_storage_after_mm`, `input_snapshot_sha256`, `controller_version`, `weather_source_version`, `seed`. Missing timestamps are failures of prospective decision-time validity, not zero values. Record the local timezone and convert timestamps to UTC without dropping offsets. Preserve raw exports separately from derived tables.

## 2. No-future-information rule
At decision time t, each controller may use only values demonstrably available by t. Require `forecast_issued_at_utc <= decision_at_utc`; require the forecast valid interval to cover the modeled period; reject any observed-rainfall input when `observation_available_at_utc > decision_at_utc`. If a controller intentionally uses oracle rainfall, label that run **oracle/perfect-information counterfactual**, exclude it from prospective efficacy claims and compare it only against an equivalently informed comparator. Never replace an unrecorded issue time with the forecast valid time.

## 3. Paired information-set equality
For each matched scenario and decision, construct a canonical sorted input manifest of weather forecasts, soil state, crop parameters and accessible history (excluding policy-specific actions). Hash the canonical manifest. Require identical exogenous manifest hash for v2 and v3 at the same decision time. Different policy-induced soil states can legitimately differ after the first decision: compare the **exogenous information set**, not endogenous state trajectories. Log mismatches, and do not silently discard them.

## 4. Water-balance audit
For a single daily soil control volume, define `delta_storage = storage_after - storage_before` and `residual = precipitation + irrigation_applied - ET_actual - runoff - drainage - delta_storage`, all expressed as **mm over the same area**. If deep capillary rise, lateral inflow/outflow, snow, or other fluxes are modeled, add their signed terms explicitly before computing residual. Irrigation **decision** is not the same as irrigation **applied**. Convert m³ to mm only with documented irrigated area: `mm = 1000 * m3 / area_m2`. A threshold for absolute and relative residual must be frozen *before* assessing results and justified against model precision; no arbitrary pass threshold is asserted here.

## 5. Twenty independently testable cases (planned, NOT executed)
| Case | Falsifiable assertion |
|---|---|
| T01 | Decision timestamp parses as offset-aware UTC |
| T02 | Forecast issue timestamp exists and is no later than decision |
| T03 | Forecast validity interval covers target horizon |
| T04 | Observation unavailable at decision is rejected as controller input |
| T05 | Missing observation availability timestamp never implies availability |
| T06 | Oracle-rainfall runs are tagged and separated |
| T07 | Exogenous input manifest is canonical and order-independent |
| T08 | Different exogenous manifests for paired policies fail equality gate |
| T09 | Policy-induced soil-state differences do not falsely fail exogenous equality |
| T10 | Identical scenario identifiers imply matched climate path and seed |
| T11 | Duplicate decision IDs within a policy/scenario/day fail |
| T12 | Missing daily flux field fails balance gate, never defaults to zero |
| T13 | Negative physically nonnegative flux is flagged with provenance |
| T14 | Storage difference uses after minus before convention |
| T15 | Irrigation decisions are not substituted for applied water |
| T16 | m³ to mm conversion requires strictly positive documented area |
| T17 | Balance residual includes every modeled lateral/capillary flux |
| T18 | Both absolute and relative residual tolerances are preregistered |
| T19 | Daily failures are preserved rather than hidden by seasonal cancellation |
| T20 | Every reported table cell carries input digest, generator SHA and analysis SHA |

## 6. Reporting table template — do not fill with invented observations
| Family | Path | Paired decisions | Ex-ante valid | Manifest matches | Balance failures | Input digest |
|---|---|---:|---:|---:|---:|---|
| C | pending original trace | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT AVAILABLE |
| R1 | pending original trace | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT AVAILABLE |

## 7. Claim gate
A passing parser on archived synthetic outcome summaries **cannot** establish forecast availability, information-set equality, or water-balance closure: the daily trace and frozen inputs are required. Until original author-controlled traces, independent SHA-256 manifests and generator replay exist, G13/G14/G15 remain **UNVERIFIED**. Even passing these gates would not constitute field validation or proof of farm-level profitability.

**References:** Allen et al., FAO-56 (1998), https://www.fao.org/4/x0490e/x0490e00.htm ; PR #1999 https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1999 . These are methodology anchors, not newly verified data sources.

No submission, email, merge, deployment, financial action or trade is authorized.

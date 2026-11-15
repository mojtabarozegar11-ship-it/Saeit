# R01 — Decision-time validity and scientific claim ledger (2026-11-15)

**Status: methodological audit protocol, NOT field evidence, NOT journal-ready.** Source: PR #1999 metadata at head 5465390203419e2ba6b6f0402d144ed29bec05e2. All reported outcomes are synthetic modeled scenarios. This note adds 20 independently auditable scientific requirements; it does not assert that they have passed.

## Critical identification defect
The controller reportedly uses realized same-day rainfall for some perfect-forecast variants. A prospective v3-v2 performance comparison is invalid if information available at the decision time differs. Treat those results as *oracle-information sensitivity analysis*, not deployable forecasts. Do not infer causal field performance or economic return.

## Twenty independent scientific evidence gates
|ID|Required evidence / verification|Pass criterion|Current evidence|
|---|---|---|---|
|01|Immutable original C archive and digest|Independent pre-existing SHA-256 matches bytes|Unverified|
|02|Immutable original R1 archive and digest|Independent pre-existing SHA-256 matches bytes|Unverified|
|03|Generator source and version|Version-pinned original source and dependencies|Unverified|
|04|Full deterministic replay|Every original record reconciles or differences documented|Unverified|
|05|Decision timestamp|Each irrigation action has recorded issue time|Unverified|
|06|Forecast issue timestamp|Forecast precedes action and is available then|Unverified|
|07|Rainfall leakage exclusion|No realized same-day rain used prospectively|Known risk; unresolved|
|08|Information parity|Both policies have same ex-ante weather information|Unverified|
|09|Unit of replication|12 paths distinguished from 540 keys/family|Documented in PR; independent audit pending|
|10|Path dependence|Inference respects path clustering|Unverified|
|11|Scenario pairing|Each v2/v3 comparison uses identical path/key|Documented in PR; independent audit pending|
|12|Missingness|All exclusions and missing cells enumerated|Unverified|
|13|Physical water balance|Input, storage, drainage, ET and residual reconcile|Unverified|
|14|Irrigation event definition|Threshold and event counting fixed before comparison|Unverified|
|15|Q98/Q100 definition|Units, threshold, period and aggregation explicit|Unverified|
|16|Drainage units|mm conversion and integration independently checked|Unverified|
|17|Climate strata|Dry/medium/wet strata defined without outcome leakage|Unverified|
|18|Multiplicity|All sensitivity weights and comparisons declared|Unverified|
|19|External calibration|Independent observed field data and error metrics|Absent in supplied PR metadata|
|20|Economic appraisal|Tariff, energy, yield, capital, risk and uncertainty verified|Absent in supplied PR metadata|

## Manuscript-safe wording
> In two synthetic irrigation scenario families (C and R1), paired postprocessing of modeled policies suggests a tradeoff between simulated threshold-exceedance days and simulated water applications. These descriptive differences are conditional on model assumptions and may be affected by asymmetric rainfall information at decision time. They do not establish field-scale water conservation, yield improvement, or profitability.

## Existing PR descriptive numbers (NOT independently reverified in this note)
|Modeled contrast (v3 minus v2)|C|R1|
|---|---:|---:|
|Q98 threshold days, mean|−4.342593|−4.794444|
|Irrigation event count, mean|+1.855556|+1.703704|
|Drainage depth, mm, mean|+13.435478|+12.016956|

## Reporting and release policy
Do not convert 3,780 modeled policy rows into 3,780 independent field replicates. Avoid confidence intervals that treat repeated paths as independent. An uncertainty estimate, if eventually used, must account for the 12 climate paths and explain the limited effective sample size. Separate synthetic results, original-model replay, independent validation and actual field data in every table caption. No paper submission, paid distribution, production deployment or merge without explicit case-specific authorization.

## Audit state at creation
- This file is a substantive methodological correction and 20-item *evidence checklist*, **0/20 newly independently verified**.
- PR head before this change: `5465390203419e2ba6b6f0402d144ed29bec05e2`.
- CI for the new commit must be fetched separately; do not infer success from an older head.

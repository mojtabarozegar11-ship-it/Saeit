# R01: independently recalculated live-workbook synthetic path sensitivity (2026-11-16)

**Status: research arithmetic cross-check only. NOT field observations, original generator replay, forecast-timing validation, peer review, journal clearance or sale eligibility.**

Source: author's current Google Sheets workbook `ZM-IRR-MODEL-2026-01 — Research Data Workbook — 4260 Records` (existing URL in README). Read-only `UNFORMATTED_VALUE` extraction of complete `CohortC1620!A1:L1621`, `RegimeR2160!A1:L2161`, and `DecisionWeights!H1:P9` on 2026-11-16. This is a **live workbook state**, not a frozen byte-for-byte independent archive; no SHA of the original author-held CSV was independently received.

## Method (pre-specified synthetic contrast)

Within each family and identical `(cohort, seed, climate_class, bias_vwc, et_forecast_multiplier, forecast_case)` key, pair `v3` with `v2` and compute Δ = v3 − v2. For each of 12 paths, average the 45 matched factorial contrasts. The finite-grid family mean is the equally weighted mean of 12 path means. Climate paths, not the 540 factorial keys, are the independent-unit candidates; even path independence/exchangeability is **not demonstrated**. No inferential confidence interval is constructed.

## Recomputed family summary (v3 − v2)

| Family | Source policy rows | Paired keys | Paths | Δ water (m³) | Δ Q100 (model days) | Δ Q98 (model days) | Δ events | Δ drainage (mm) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| C | 1620 | 540 | 12 | 36.068956 | -6.892593 | -4.342593 | 1.855556 | 13.435478 |
| R1 | 2160 | 540 | 12 | 30.575281 | -7.470370 | -4.794444 | 1.703704 | 12.016956 |

**Interpretation:** in BOTH simulated families v3 increased gross water applied, irrigation event counts, and modeled drainage depth while reducing model Q100/Q98 threshold-day counts. This is a model tradeoff; **not** a demonstrated water-saving intervention or farm benefit.

## All 24 climate-path paired means (45 synthetic factorial settings per path)

| Family/path | Seed | Class | Δ water m³ | Δ Q100 days | Δ Q98 days | Δ events | Δ drainage mm |
|---|---:|---|---:|---:|---:|---:|---:|
| C-dry-1 | 919 | dry | 0.000000 | -12.222222 | -8.488889 | 0.000000 | 0.000000 |
| C-dry-2 | 1111 | dry | 17.266280 | -9.022222 | -5.133333 | 1.733333 | 7.357596 |
| C-dry-3 | 1212 | dry | 20.361573 | -7.422222 | -5.244444 | 2.022222 | 4.505510 |
| C-dry-4 | 1313 | dry | 0.000000 | -11.466667 | -7.688889 | 0.000000 | 0.000000 |
| C-medium-1 | 1919 | medium | 11.612703 | -13.888889 | -9.044444 | 1.333333 | 1.349054 |
| C-medium-2 | 2111 | medium | 40.614037 | -9.466667 | -5.111111 | 1.755556 | 5.517418 |
| C-medium-3 | 2212 | medium | 33.190314 | -7.911111 | -5.533333 | 2.022222 | 8.003320 |
| C-medium-4 | 2313 | medium | 72.370457 | -2.422222 | -1.088889 | 3.177778 | 31.169349 |
| C-wet-1 | 2919 | wet | 55.546701 | -4.800000 | -2.933333 | 2.444444 | 13.504492 |
| C-wet-2 | 3111 | wet | 80.936538 | 0.000000 | 0.000000 | 3.488889 | 34.411288 |
| C-wet-3 | 3212 | wet | 35.422529 | 0.000000 | 0.000000 | 1.488889 | 12.981791 |
| C-wet-4 | 3313 | wet | 65.506340 | -4.088889 | -1.844444 | 2.800000 | 42.425921 |
| R-dry-1 | 173 | dry | 26.472833 | -9.911111 | -6.622222 | 2.044444 | 7.630821 |
| R-dry-2 | 347 | dry | 20.737232 | -9.111111 | -5.733333 | 2.000000 | 3.822856 |
| R-dry-3 | 521 | dry | 0.000000 | -11.266667 | -7.222222 | 0.000000 | 0.507007 |
| R-dry-4 | 695 | dry | 50.389957 | -6.333333 | -4.133333 | 2.466667 | 11.820096 |
| R-medium-1 | 2173 | medium | 56.311644 | -7.911111 | -5.177778 | 3.288889 | 28.777220 |
| R-medium-2 | 2347 | medium | 20.105635 | -11.466667 | -8.066667 | 1.733333 | 4.053971 |
| R-medium-3 | 2521 | medium | 5.932169 | -12.200000 | -7.755556 | 0.688889 | 2.574534 |
| R-medium-4 | 2695 | medium | 66.470495 | -6.844444 | -3.311111 | 2.822222 | 17.711798 |
| R-wet-1 | 4173 | wet | 19.231343 | 0.000000 | 0.000000 | 0.822222 | 15.962015 |
| R-wet-2 | 4347 | wet | 40.360511 | -9.088889 | -5.600000 | 1.977778 | 3.111180 |
| R-wet-3 | 4521 | wet | 42.210944 | -5.511111 | -3.911111 | 1.822222 | 32.727066 |
| R-wet-4 | 4695 | wet | 18.680613 | 0.000000 | 0.000000 | 0.777778 | 15.504909 |

## Path-level variation and leave-one-path-out influence

Deterministic LOO mean: \u0394_{-p}=(\u03a3_{q\u2260p}D_q)/11. Influence: full-path mean minus LOO mean. The SD and SE below describe dispersion **only**; they do not imply an external-population interval without a sampling model.

| Family | Outcome | Descriptive path SD | SD/√12 (descriptive) | Largest absolute LOO influence | Sign reversed by any deletion? |
|---|---|---:|---:|---:|---|
| C | Δ applied gross water (m³) | 27.644683 | 7.980332 | 4.078871 | no |
| C | Δ Q100 (model plot-days) | 4.651431 | 1.342752 | 0.636027 | no |
| C | Δ Q98 (model plot-days) | 3.169077 | 0.914834 | 0.427441 | no |
| C | Δ irrigation events (model count) | 1.088312 | 0.314168 | 0.168687 | no |
| C | Δ drainage summed depth (mm) | 14.494908 | 4.184320 | 2.635495 | no |
| R1 | Δ applied gross water (m³) | 20.471970 | 5.909749 | 3.263201 | no |
| R1 | Δ Q100 (model plot-days) | 4.060351 | 1.172122 | 0.679125 | no |
| R1 | Δ Q98 (model plot-days) | 2.693070 | 0.777422 | 0.435859 | no |
| R1 | Δ irrigation events (model count) | 0.963269 | 0.278072 | 0.154882 | no |
| R1 | Δ drainage summed depth (mm) | 10.534601 | 3.041077 | 1.882737 | no |

## Arithmetic verification against original workbook DecisionWeights

Recalculated 8 λ values (0, 1, 2, 5, 10, 20, 50, 100) for each family, including v3/v2/tie counts and mean Δ[V + λ Q100]. All **64 numeric source-sheet comparisons** agreed within 1e-8 for means and exactly for counts. This checks arithmetic consistency **inside the same workbook**, not independence of its underlying simulation or generator.

| Family | λ | v3 favored | v2 favored | ties | Mean ΔL (model proxy, not profit) |
|---|---:|---:|---:|---:|---:|
| C | 0 | 20 | 383 | 137 | 36.068956 |
| C | 1 | 117 | 334 | 89 | 29.176363 |
| C | 2 | 136 | 315 | 89 | 22.283771 |
| C | 5 | 161 | 290 | 89 | 1.605993 |
| C | 10 | 196 | 255 | 89 | -32.856970 |
| C | 20 | 213 | 238 | 89 | -101.782896 |
| C | 50 | 217 | 234 | 89 | -308.560674 |
| C | 100 | 222 | 229 | 89 | -653.190303 |
| R1 | 0 | 13 | 401 | 126 | 30.575281 |
| R1 | 1 | 115 | 331 | 94 | 23.104911 |
| R1 | 2 | 144 | 302 | 94 | 15.634541 |
| R1 | 5 | 185 | 261 | 94 | -6.776570 |
| R1 | 10 | 193 | 253 | 94 | -44.128422 |
| R1 | 20 | 204 | 242 | 94 | -118.832126 |
| R1 | 50 | 214 | 232 | 94 | -342.943237 |
| R1 | 100 | 214 | 232 | 94 | -716.461756 |

## What was and was not verified

- VERIFIED IN THIS LIVE READ: exactly 1,620 C and 2,160 R1 synthetic policy rows; two sets of 540 complete v2/v3 paired keys; 12 path IDs per family; 45 settings/path; four paths/class; no duplicate `(key, policy)`; 24 path-mean summaries; 64 worksheet consistency checkpoints.
- NOT VERIFIED: independently escrowed source CSV hashes; regenerated weather/controller daily trajectories; forecast issued-at-action timestamps; oracle-vs-ex-ante information parity; daily root-zone water-balance closure; field observations/crop yield; regional representativeness; economic costs and prices; author rights; journal approval.
- The separate `path_cluster_sensitivity.py` and `test_path_cluster_sensitivity.py` are source/fixture-based validation code; their 32 authored regression tests cannot be called passing until exact-commit CI evidence is available.
- No submission, sale, delivery, customer outreach, merge, hosting change, wallet transfer, live trade or cost is authorized by this supplement.

**Release: HOLD / SIMULATION ONLY.**

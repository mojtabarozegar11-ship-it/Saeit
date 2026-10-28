# AE-2026-001 C27 — Horizon-induced growth-sign reversals: exact threshold and margin sensitivity

**Date:** 27 October 2026. **Status:** new source-row-level secondary analysis on the previously archived official 2026 WDI panel, **not** new raw data, independent employment validation, a novel estimator or a causal claim. Internal AI analysis, not human peer review.

## Source and estimand
The complete committed `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv` was read from `research/mr-2026-001-novelty-audit`, blob SHA `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9` (source-file SHA256 previously recorded as `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`). CSV fields were parsed with quoted-field handling. From 217 nonaggregate economies, retain the **153** with positive finite 2000, 2019 and 2023 values. This is **not** the distinct fixed 155-economy three-vintage cohort.

For each economy define E = 100 log(P2019/P2000)/19, L = 100 log(P2023/P2019)/4, H = 100 log(P2023/P2000)/23, in annual log-percentage points. E→L compares two **nonoverlapping periods**; E→H compares **overlapping horizons**. A sign switch requires strictly opposite signs. Margin threshold m requires the absolute growth rates **on both sides of that specific comparison** to be strictly greater than m. All margins were selected post hoc as diagnostics, not significance tests.

## Exact condition for an overlapping-horizon sign reversal
Since 23H = 19E + 4L, if E and L have opposite signs and E is nonzero, E and H have opposite signs **if and only if** `|L| > (19/4)|E| = 4.75|E|`. Equality makes H zero, not a strict opposite sign. This algebraic requirement explains why an early-versus-late sign switch does not necessarily survive extension of the horizon to 2023. It is a mathematical identity, **not a new empirical estimator**.

## New source-rowwise margin audit
| Strict absolute margin on both compared rates (log-pp/year) | E→L sign switches (n/153) | E→H sign switches (n/153) |
| ---: | ---: | ---: |
| 0 | 60 | 10 |
| 0.1 | 54 | 6 |
| 0.2 | 51 | 6 |
| 0.5 | 42 | 3 |
| 1.0 | 33 | 1 |
| 2.0 | 18 | 0 |

**New empirical finding:** of the ten overlapping-horizon growth-sign reversals, **seven have at least one compared annual rate with absolute magnitude ≤0.5 log-pp/year**, and only **one** exceeds 1 log-pp/year on both sides. By contrast, 42 of 60 early-versus-late switches exceed 0.5 on both sides. Thus the headline 10/153 is highly sensitive to how small growth rates are treated. The two columns are **different estimands**, not two vintage revision counts. Do not interpret a smaller E→H count as stronger underlying stability or a global trend.

### All ten E→H cases, rounded for display
| ISO3 | E (2000–2019) | L (2019–2023) | H (2000–2023) | min(|E|,|H|) |
| --- | ---: | ---: | ---: | ---: |
| BWA | +0.00162 | −7.61624 | −1.32322 | 0.00162 |
| JPN | −0.01607 | +2.73865 | +0.46302 | 0.01607 |
| TON | −0.03847 | +8.79390 | +1.49759 | 0.03847 |
| SLV | −0.06448 | +1.08038 | +0.13463 | 0.06448 |
| LUX | +0.29643 | −13.64404 | −2.12800 | 0.29643 |
| BLZ | −0.34243 | +4.94497 | +0.57712 | 0.34243 |
| SGP | −0.49553 | +8.11913 | +1.00267 | 0.49553 |
| ARE | −2.26245 | +14.16366 | +0.59426 | 0.59426 |
| CUB | +0.76318 | −12.83094 | −1.60102 | 0.76318 |
| BRN | −1.08306 | +12.57840 | +1.29284 | 1.08306 |

## Reproduction and critical limitations
From the committed CSV, parse quoted fields, retain 153 positive finite endpoint triples, calculate E/L/H as above, test `E*L < 0` and `E*H < 0` with strict margin filters `abs(E)>m && abs(L)>m` and `abs(E)>m && abs(H)>m`. This was recomputed in the connected GitHub analysis session; no separate GitHub Actions run is claimed. Thresholds were not preregistered, small-rate classification is not statistical significance, and no measurement uncertainty model was estimated. The early 19-year and late 4-year rates differ in horizon, macroeconomic shocks and coverage. This does **not** validate a causal break, historical vintage revisions, a new method, or external generalizability. In particular, do not conflate the ten E→H switches (153-economy 2026-only sample) with the ten 2024→2026 release switches (155-economy historical-vintage sample).

**Cross-check of earlier repository evidence:** C13 identifies SDN, SYR, PSE and UKR as 2000/2019-positive but 2023-absent, while C14's eight masks sum to 217 with 153 fully observed. These were read directly from the branch and are **prior-cycle results**, not new successes.

**AI disposition:** add as transparent exploratory sensitivity in the consolidated author-review manuscript; preserve **MAJOR REVISION / NO SUBMISSION**. No publication, author approval or live-site deployment.

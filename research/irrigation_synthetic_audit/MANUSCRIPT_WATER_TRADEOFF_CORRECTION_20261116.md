# R01 manuscript correction: no demonstrated irrigation-water saving (2026-11-16)

**Status:** author-facing, source-only correction for a **synthetic** workbook. Not field evidence, independent generator replay, a publication, or a commercial product. No submission is authorized.

## Research question and unit of analysis

Compare modeled policy v3 against v2 within each family, pairing on identical climate path, seed, climate class, sensor bias, ET multiplier and rainfall-information case. The finite-grid contrast is Δ = outcome(v3) − outcome(v2). The 540 matched factorial settings per family share 12 modeled climate paths; they are **not** 540 independently randomized farms. Summaries below are descriptive and do not carry inferential confidence intervals.

## Reproducible arithmetic from the already documented 2026-11-16 live-workbook read

The immediate source is `LIVE_WORKBOOK_PATH_SENSITIVITY_20261116.md` in this PR (read-only workbook extraction of CohortC1620, RegimeR2160 and DecisionWeights). This document does **not** assert a new independent data download or source freeze.

| Simulated family | Policy rows | Paired keys | Climate paths | Δ applied gross water (m³) | Δ modeled Q100 threshold-days | Δ modeled Q98 threshold-days | Δ events | Δ drainage depth (mm) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| C | 1,620 | 540 | 12 | +36.068956 | −6.892593 | −4.342593 | +1.855556 | +13.435478 |
| R1 | 2,160 | 540 | 12 | +30.575281 | −7.470370 | −4.794444 | +1.703704 | +12.016956 |

**Mandatory claim correction:** v3 applied **more**, not less, modeled gross irrigation water in both families. It reduced the modeled Q100 and Q98 below-threshold-day proxies. The outcome cannot be called measured water savings, higher crop yield, improved irrigation efficiency, or net economic benefit. Drainage depth is reported in **mm**, not m³; conversion to volume requires a documented spatial area and physical interpretation.

## Explicit proxy-loss crossover (derived, not fitted)

For the illustrative loss `L = V + λ Q100`, where V is gross applied water in m³ and Q100 is a model threshold-day count, the family-average contrast is `ΔL = ΔV + λ ΔQ100`. The descriptive family-average zero crossing is `λ* = −ΔV/ΔQ100` when `ΔQ100 ≠ 0`. It is a **ratio of means**, not the mean or median of scenario-specific crossover weights. Its dimensional unit is m³ per modeled threshold-day, **not currency, crop price or profit**.

| Family | ΔV | ΔQ100 | λ* (approx. m³/model threshold-day) | Interpretation |
|---|---:|---:|---:|---|
| C | +36.068956 | −6.892593 | 5.233 | λ below threshold favors v2 in the family-average proxy; above favors v3 |
| R1 | +30.575281 | −7.470370 | 4.093 | same conditional proxy interpretation |

These ratios use rounded source-table means; report as approximations, not exact scenario decisions. The family-specific signs are not a causal claim and cannot be generalized to farms.

## Twenty distinct manuscript acceptance checks (pending independent evidence)

| ID | Required verification | Current status |
|---|---|---|
| 01 | Original author-held source export and independently preserved SHA-256 | NOT PROVEN |
| 02 | Exact 1,620 C source policy records | Live-workbook arithmetic only |
| 03 | Exact 2,160 R1 source policy records | Live-workbook arithmetic only |
| 04 | 540 complete policy-paired keys in C | Live-workbook arithmetic only |
| 05 | 540 complete policy-paired keys in R1 | Live-workbook arithmetic only |
| 06 | 12 unique path/seed identifiers per family | Live-workbook arithmetic only |
| 07 | 45 factorial settings per path | Live-workbook arithmetic only |
| 08 | Four paths per dry/medium/wet class | Live-workbook arithmetic only |
| 09 | No duplicate (key,policy) records | Live-workbook structural check only |
| 10 | v3−v2 water sign and m³ unit | Derived from documented workbook |
| 11 | v3−v2 Q100 sign and modeled-day unit | Derived from documented workbook |
| 12 | v3−v2 Q98 sign and modeled-day unit | Derived from documented workbook |
| 13 | v3−v2 event count sign | Derived from documented workbook |
| 14 | Drainage depth in mm, never mislabeled volume | Manuscript correction specified |
| 15 | Ratio-of-means crossover not misreported as median | Manuscript correction specified |
| 16 | Decision-time issued forecasts independently timestamped | NOT PROVEN |
| 17 | No realized future rainfall leaked into action-time decisions | NOT PROVEN |
| 18 | Day-level root-zone water-balance closure and generator replay | NOT PROVEN |
| 19 | Independent farm/field crop-yield and cost validation | NOT PROVEN |
| 20 | Author permissions, editorial disclosures and journal clearance | NOT PROVEN |

**Publication gate: HOLD.** Source consistency checks within the same workbook are not independent provenance checks. There is no demonstrated population sampling design, independently validated forecast information parity, field measurement, profit or customer sale. Any manuscript abstract/conclusion claiming measured conservation or commercial performance must be corrected before review.

No email, article submission, merge, deployment, trade, wallet transaction or expense was performed by this document.

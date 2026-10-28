# AE-2026-001 C25 — Paired-country robustness and dispersion for nonoverlapping growth periods

**27 October 2026.** New direct computation from the 217-row official 2026 WDI country CSV on the specified research branch (GitHub blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`). This analysis is **not** historical WDI vintage revision, a causal estimate, a population-weighted global trend or independent ILO employment validation.

## Locked population and estimand
Keep **153** economies with positive finite agricultural value-added-per-worker observations at **2000, 2019 and 2023**, using ISO3 and country region from the source. For each country calculate `g_long=100*ln(y2019/y2000)/19`, `g_short=100*ln(y2023/y2019)/4`, and the **within-country difference** `d=g_short-g_long` (annual log-percentage points). **Do not** subtract the medians of different cohorts or treat these unequal period lengths as identical exposure.

## Fresh calculations (independently recomputed on all 153 source rows)
| Metric | 2000–2019 annual growth | 2019–2023 annual growth | Paired d |
|---|---:|---:|---:|
| Mean | 2.402070624 | 0.541735421 | **−1.860335203** |
| Median | 2.355575295 | 0.890439534 | **−1.925831615** |
| Median absolute deviation (unscaled) | 1.592396666 | 2.449445315 | **2.328624667** |
| Interquartile range (linear-interpolated quartiles) | 3.200344194 | 4.924863253 | **4.521019119** |

- Short-period cross-country MAD is **1.538** times long-period MAD (2.449445315/1.592396666). This is a **descriptive scale comparison**, not a variance test; a four-year growth annualization may be more volatile for many reasons.
- Paired-difference quartiles: **Q1 −4.118226068**, **Q3 +0.402793052** log-pp/year. Ten-percent symmetric trimmed mean of paired d: **−1.837483236**.
- **109/153** countries have negative d, **44/153** positive, zero ties. This reproduces C23's direction census; **do not count the 109/44 census as a fresh discovery**.

## Two newly computed resampling sensitivities
Both use **10,000** iterations, deterministic **xorshift32** pseudo-random generator with initial unsigned 32-bit seed **20261027**; each draw uses `floor(u*n)`, `u` in [0,1). Median is the central order statistic or average of two central values; percentile interpolation uses position `(n-1)*q`.

1. **Country resampling:** sample 153 paired differences with replacement each iteration. The 2.5th–97.5th percentile interval for the **resampled median** is **[−2.540285, −1.382149]** log-pp/year.
2. **Region-cluster resampling:** sample seven WDI regions with replacement, keep **all countries** in each sampled region (regions with different sizes thus contribute different counts), and recompute pooled median. The analogous sensitivity interval is **[−2.538920, −0.785653]** log-pp/year. Region sizes: Europe/Central Asia 45; MENA/Afghanistan/Pakistan 15; Latin America/Caribbean 28; East Asia/Pacific 22; Sub-Saharan Africa 36; South Asia 6; North America 1.

**Critical inference limit:** These are **conditional resampling distributions of this selected panel**, not validated 95% confidence intervals for global agricultural productivity, independent-country sampling, a causal post-2019 break or historical WDI vintage effects. Seven region clusters are far too few to claim reliable cluster-robust inferential coverage; within-region dependence, unequal period length, country selection and non-random missingness remain unresolved. The sign and median direction are robust **within these descriptive resampling schemes**, not across all defensible economic designs.

## Reproduction specification
Parse CSV as RFC4180 quoted records; filter positive finite numeric endpoint triplets; compute growth and d; sort for medians/quartiles; 10,000 resamples with the above PRNG, sampling order country rows as in the locked CSV and region order as **first occurrence** in that file; compute linear-interpolated quantiles of 10,000 replicate medians. No missing value is replaced by zero. No new source download or invented observation was used.

**Internal AI verdict:** supplementary sensitivity evidence only; **MAJOR REVISION / NO SUBMISSION**. Historical ILOSTAT vintages, actual three-vintage countryatlas benchmark, novelty and human author approval remain open.

# AE-2026-001 C26 — Exact reconciliation of overlapping-horizon and nonoverlapping-period growth comparisons

**Date:** 2026-10-27. **Status:** original source-file recomputation and an exact algebraic identity, not a new statistical estimator, historical WDI-vintage comparison, causal claim, or independent employment measurement.

## Source and inclusion
The complete original 217-economy source CSV `research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv` was fetched from branch `research/mr-2026-001-novelty-audit`, GitHub blob SHA `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`, previously recorded SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`. After parsing RFC4180 quoted fields, retain only positive finite observations at 2000, 2019 and 2023: **153** economies. The source population is **not** the distinct 155-economy fixed historical-vintage sample.

## Exact mathematical identity
For each economy i define annual log-percentage-point growth:

- `E_i = 100 ln(P_2019/P_2000)/19`, early 2000–2019 rate;
- `L_i = 100 ln(P_2023/P_2019)/4`, late 2019–2023 rate;
- `H_i = 100 ln(P_2023/P_2000)/23`, entire 2000–2023 rate.

By the logarithm product identity, **`23 H_i = 19 E_i + 4 L_i`**. Thus **`H_i − E_i = (4/23)(L_i − E_i)`** for *every* economy with valid endpoints. This is an exact weighted-rate relationship, not an empirical causal mechanism. It shows that the overlapping-horizon comparison (2000–2019 versus 2000–2023) attenuates the nonoverlapping-period rate contrast by exactly **4/23 = 0.173913043478**.

Because the multiplier is strictly positive, the *direction of the paired rate change* is identical for the two contrasts; however, **the number of countries whose *growth-rate sign* changes is not identical**. In particular, a change of sign between E and H implies a sign change between E and L, but the converse is false because H is a weighted average dominated by E.

## Fresh direct numerical reconciliation from source CSV
| Statistic | Recomputed value |
| --- | ---: |
| Fully observed economies | 153 |
| Median E, 2000–2019 (log-pp/year) | 2.3555752946417114 |
| Median L, 2019–2023 (log-pp/year) | 0.8904395335439335 |
| Median H, 2000–2023 (log-pp/year) | 2.224483704398673 |
| Median paired (L − E) (log-pp/year) | −1.9258316149146344 |
| Median paired (H − E) (log-pp/year) | −0.3349272373764576 |
| Exact multiplier × median (L − E) | −0.33492723737645813 |
| Mean paired (H − E) | −0.3235365569669903 |
| Negative paired change | 109 |
| Positive paired change | 44 |
| E→L growth-sign switches | 60 |
| E→H growth-sign switches | 10 |
| E→L switches without E→H switch | 50 |
| Maximum absolute rowwise identity residual (log-pp/year) | 1.9984014443252818e−15 |

The **10** E→H sign-switch ISO3 keys are **ARE, BLZ, BRN, BWA, CUB, JPN, LUX, SGP, SLV, TON**. They form a subset of the 60 E→L sign-switch cases. The 109/44 directions and the paired median −1.9258316 reproduce previously recorded C23/C25 results and **are not separately claimed as fresh discoveries**. Likewise the −0.3349272 overlapping-horizon median was known in the earlier horizon sensitivity; the *new contribution in this audit is the explicit algebraic reconciliation, source-rowwise identity test and 10/60 subset explanation*.

**Crucial non-equivalence:** `median(H−E)` is not `median(H)−median(E)`: here the latter is **−0.1310915902430384**, not −0.3349272373764576. Likewise the 153-economy medians must not be compared with the separate 155-economy three-vintage medians as if the samples and estimands were identical.

## Reproduction and scientific limitations
Read the committed CSV with an RFC4180 parser; filter positive finite endpoint triples; compute E, L, H with the formulas above; test `abs((H−E)−(4/23)*(L−E)) < 1e−12` on every row; calculate country-level medians and sign-switch sets by strict sign comparisons, with no imputation. This source-rowwise calculation was executed in the connected GitHub tool session, **not in a separately verified GitHub Actions job**. It uses the already archived 2026 release only and does not independently execute the countryatlas `compare_vintages` method. The identity is a basic property of logarithmic growth; it is not methodological novelty, evidence of a post-2019 structural break, global-representative inference or historical revision causality.

**AI scientific disposition:** explanatory and error-prevention analysis suitable for Methods/Results, not a new publishable standalone finding. **MAJOR REVISION / NO SUBMISSION.**

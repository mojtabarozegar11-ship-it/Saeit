# AE-2026-001 C11 — Region-by-matching concentration decomposition (post hoc)
**Date:** 26 October 2026. **Status:** independently recomputed *derived* arithmetic from the already verified 157-economy regional summary; **not** a new primary-data extract, historical ILOSTAT vintage or population-level inference.

## Provenance and estimand
The input is the seven region-level matched/total counts already produced by the **source-locked original-country** run [40317629788](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40317629788), [artifact 12647203753](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40317629788/artifacts/12647203753), and recorded in C9/Methods 2.9/Results 3.18. Input hashes for that earlier source run: worker-growth JSON `3feee3649062338bc55489019791cbddde608714eb4ab7837dde486f710c28a8`; archived WDI 2026 panel `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`. This C11 recomputation uses **published aggregate counts** only and cannot independently validate country classifications.

| WDI region | Matched | Unmatched | Total | Matched share |
|---|---:|---:|---:|---:|
| Europe/Central Asia | 32 | 14 | 46 | 69.57% |
| Latin America/Caribbean | 16 | 12 | 28 | 57.14% |
| East Asia/Pacific | 12 | 10 | 22 | 54.55% |
| Middle East/North Africa/Afghanistan/Pakistan | 6 | 11 | 17 | 35.29% |
| South Asia | 2 | 4 | 6 | 33.33% |
| Sub-Saharan Africa | 4 | 33 | 37 | 10.81% |
| North America | 1 | 0 | 1 | 100% (n=1; not population inference) |
| **Total** | **73** | **84** | **157** | **46.50%** |

## New derived decomposition
Under the *within-this-fixed-panel* no-association table, the expected matched count for region r is `E[r,matched] = region_total[r] * 73 / 157`. The Pearson statistic is the sum over the 14 cells of `(O-E)^2/E`.

- **Full 7×2 Pearson chi-square = 33.0552747497**, matching the original source-locked analysis to rounding. Degrees of freedom = 6. **This is an arithmetic check**, not a new hypothesis test.
- **Sub-Saharan Africa contributes 18.9406 (57.30%) of the total chi-square** across its matched and unmatched cells. Expected matched = **17.2038**; observed matched = **4**; matched-cell Pearson residual **−3.183**.
- **Europe/Central Asia contributes 9.8399 (29.77%)** of the total. Expected matched = **21.3885**; observed = **32**; matched-cell residual **+2.294**.
- Together, those two regions account for approximately **87.07%** of the observed Pearson association statistic. The remaining five regions jointly contribute about **12.93%**.
- The observed **Europe/Central Asia vs Sub-Saharan Africa coverage ratio** is `(32/46)/(4/37) = 6.4348`. Their descriptive 2×2 odds ratio is `(32×33)/(14×4) = 18.8571`. These are **within-panel effect-size descriptions**, not population risk/odds ratios.
- At least the North America row has expected matched/unmatched cell counts **below 1** (0.4650/0.5350); the South Asia row has expected cells below 5. Thus a conventional **asymptotic chi-square p-value is not reliable**. The earlier source-locked **10,000-label-permutation** tail diagnostic (0 exceedances, +1 corrected `1/10001`) is preferable for a conditional within-panel description, but still relies on a hypothetical exchangeability null, post-hoc selection, and **cannot** establish random sampling, global significance or the cause of missing data.

## Sparse-singleton sensitivity: exclude North America (n=1)

As a prespecified-in-this-audit *diagnostic*, recompute the same Pearson association after **excluding** the single North America economy rather than treating 1/1 as an interpretable regional rate. The remaining **156 economies** contain **72 matched** and **84 unmatched** across six regions. Direct recomputation gives **chi-square = 31.9295650604** (5 degrees of freedom), **Cramer's V = sqrt(31.9295650604/156) = 0.4524121** versus 0.45885 in the seven-region table. Sub-Saharan Africa contributes **18.5972** of this six-region statistic (approximately **58.2%**). The descriptive concentration finding therefore does **not** depend on the singleton row. This is not a fresh source observation, a preregistered sensitivity, or a license to interpret the asymptotic chi-square p-value: South Asia still has expected cells below five and the entire country set remains nonrandom.

## Scientific interpretation and publication gate
This derived decomposition identifies *which regions drive the existing descriptive imbalance*: the underrepresentation of Sub-Saharan African economies is the largest contributor. It does **not** cure missingness, produce new source-country observations, validate historical 2024/2025 ILO employment vintages, show causal selection, or establish originality over countryatlas. Do not infer any 155-economy historical-vintage population claim from the 73 matched current-source economies. Keep **MAJOR REVISION / NO SUBMISSION** until genuine novelty and historical provenance gates are addressed.

# AE-2026-001 C19 — Exact 16-economy influence and mean-gap attribution

**26 October 2026 | New analysis of existing source-locked WDI observations | Exploratory and post hoc**

## Research question and source
How much of the equal-economy 2019–2023 mean growth gap between the 153 three-endpoint economies and the 169 two-endpoint economies is algebraically associated with each of the 16 additional economies?

Original 217-economy WDI CSV: `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`, SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`. Recomputed directly from the GitHub CSV with the annual growth definition `g_i = 25 ln(P_2023/P_2019)` log percentage points/year. No additional data collection, no ILOSTAT historical-vintage comparison, no new estimator.

## Exact additive identity
Let `B` be the 153 complete 2000/2019/2023 economies and `A` the 16 with 2019/2023 observations but no positive 2000 observation. Define `mu_B = mean(g in B)` and `mu_P = mean(g in B union A)`. Then:

`mu_P - mu_B = (sum_{i in A} (g_i - mu_B)) / 169`.

The 16 terms sum to the observed gap exactly, with no residual. These are **baseline-relative arithmetic contributions**, **not causal effects**, causal missingness mechanisms, or uniquely defined economic contributions.

## Directly recomputed results

- Baseline `n=153` mean **0.5417354215**, pooled `n=169` mean **0.8101423204**; gap **+0.2684068989** log-pp/year.
- Baseline median **0.8904395335**, pooled median **0.9751104652**.
- CAF (`g=+28.1537951`) contributes **+0.1633849683** log-pp/year to the mean gap under this identity.
- DJI (`g=+17.2598396`) contributes **+0.0989236933** log-pp/year.
- The two baseline-relative contributions sum to **+0.2623086616**, **97.72799%** of the observed net +0.2684068989 gap. Because other positive and negative contributions offset, this percentage **must not be interpreted as an invariant share of an economic causal effect**.
- Removing only CAF from the pooled set **post hoc** gives mean **0.6473824827**; removing only DJI gives **0.7122274557**. Neither observation is removed in the primary analysis.
- Single-deletion pooled medians are **0.9327750** when deleting one of the nine added economies above the pooled median and **0.9894295** when deleting one of the seven below it; the median changes much less than the mean in this particular diagnostic. These are order-statistic properties of the same fixed data, not a population robustness guarantee.

| Added economy | Annual log growth | Baseline-relative contribution to mean gap | Pooled mean after deleting only this economy |
|---|---:|---:|---:|
| CAF | +28.153795 | +0.163385 | 0.647382 |
| DJI | +17.259840 | +0.098924 | 0.712227 |
| GHA | +6.695085 | +0.036410 | 0.775113 |
| TKM | +5.600739 | +0.029935 | 0.781627 |
| LBY | +5.006519 | +0.026419 | 0.785164 |
| KWT | +4.936957 | +0.026007 | 0.785578 |
| BHR | +4.582374 | +0.023909 | 0.787689 |
| GEO | +4.152609 | +0.021366 | 0.790247 |
| AGO | +1.193767 | +0.003858 | 0.807859 |
| GNQ | +0.423996 | −0.000697 | 0.812441 |
| CIV | +0.256922 | −0.001685 | 0.813435 |
| TCD | −2.621610 | −0.018718 | 0.830569 |
| PNG | −4.319005 | −0.028762 | 0.840673 |
| AFG | −4.413906 | −0.029323 | 0.841238 |
| STP | −5.503479 | −0.035771 | 0.847723 |
| SLB | −7.376069 | −0.046851 | 0.858870 |

## Interpretation, originality and evidence limitations
1. This analysis complements C15/C16/C18 by exposing the **exact country-level arithmetic**, not just a two-country exclusion or a regional shift-share split. It **does not establish a publishable original statistical method** or a mechanism for why values are missing.
2. The share 97.73% is **reference-dependent** (relative to baseline mean) and can exceed 100% in other data due to cancellation. It is not a proportion of variance or causal attribution.
3. The 16 economies are selected by 2000 endpoint availability; no representative-world, probability-sampling, independence, or missing-at-random assumption is justified.
4. CAF and DJI have large observed log growth, but no source evidence proves data errors or warrants dropping them. Any exclusion is explicitly **post hoc**.
5. `analysis/ae_2026_001_c19_added_economy_influence.py` reproduces all 16 entries from source bytes with a SHA256 gate, 217/153/16 cardinality gates and exact sum identity; the script's execution in GitHub Actions is **not claimed** here.
6. This does not resolve historical ILOSTAT 2024/2025 vintages, WDI source overlap or the numerical countryatlas benchmark. **MAJOR REVISION / NO SUBMISSION**.

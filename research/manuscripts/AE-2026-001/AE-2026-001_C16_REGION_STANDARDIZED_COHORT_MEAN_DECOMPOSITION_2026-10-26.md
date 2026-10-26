# AE-2026-001 C16 — Region-standardized decomposition of 2019–2023 cohort mean shift

**Analysis date:** 26 October 2026. **Status:** newly computed, exploratory descriptive research analysis; **MAJOR REVISION / NO SUBMISSION**. **Input:** version-controlled official WDI observed-country panel `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`, indicator `NV.AGR.EMPL.KD`, 217 nonaggregate economies. **Locked input SHA256:** `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`.

## Scientific question

How much of the difference between the equal-economy mean annual 2019–2023 agricultural value-added-per-worker growth in the 153-economy three-endpoint panel and the 169-economy 2019/2023 sample is mechanically due to **changing region shares** versus **changing within-region sample means**? This is a descriptive accounting question, **not** a causal explanation of missing 2000 data, regional economic shocks, WDI revision, or a new statistical estimator.

## Methods and exact identity

For economy i with positive 2019 and 2023 endpoints, `g_i = 100 ln(P_i,2023/P_i,2019)/4` annual log-percentage points. Baseline B contains 153 economies positive in 2000/2019/2023. P contains all 169 economies positive in 2019/2023; 16 additional economies lack the positive 2000 endpoint. For each official World Bank region r, let `w_B,r = n_B,r/153`, `w_P,r = n_P,r/169`, `m_B,r` and `m_P,r` be equal-country regional means. The **exact descriptive identity** is:

`mean_P - mean_B = sum_r[(w_P,r - w_B,r) m_B,r] + sum_r[w_P,r (m_P,r - m_B,r)]`.

The first term is **region-composition reweighting** at baseline regional means; the second is **within-region sample-mean replacement**. The decomposition is baseline-reference-dependent, not unique, causal, or a historical-vintage decomposition. All seven regions had at least one baseline economy.

## Actual computed results

| Region | Baseline n | Pooled n | Baseline mean log-pp/y | Pooled mean log-pp/y | Composition contribution | Within-region contribution |
|---|---:|---:|---:|---:|---:|---:|
| East Asia & Pacific | 22 | 24 | +2.454104 | +1.762300 | −0.004366 | −0.098244 |
| Europe & Central Asia | 45 | 47 | +0.819840 | +0.992471 | −0.013127 | +0.048010 |
| Latin America & Caribbean | 28 | 28 | +0.080317 | +0.080317 | −0.001392 | 0 |
| Middle East, North Africa, Afghanistan & Pakistan | 15 | 20 | −0.753081 | +0.803779 | −0.015291 | +0.184244 |
| North America | 1 | 1 | +3.725433 | +3.725433 | −0.002305 | 0 |
| South Asia | 6 | 6 | +1.010125 | +1.010125 | −0.003750 | 0 |
| Sub-Saharan Africa | 36 | 43 | −0.242678 | +0.461908 | −0.004646 | +0.179274 |
| **Exact total** | **153** | **169** | **+0.541735** | **+0.810142** | **−0.044876** | **+0.313283** |

**Identity check:** `0.8101423204 − 0.5417354215 = +0.2684068989 = −0.0448759266 + 0.3132828255` log-pp/year, within floating-point tolerance. Thus the observed pooled mean increase is **not** primarily explained by the changed regional weights; it is dominated by changes in the observed sample means **within** regions, especially Middle East/North Africa (+0.184244) and Sub-Saharan Africa (+0.179274), partly offset by East Asia/Pacific (−0.098244). **This does not establish why the added economies have different growth values.**

## Post-hoc influential-case sensitivity

The previously identified added-cohort observations CAF (+28.1538) and DJI (+17.2598) are *not removed from the primary analysis*. If they are excluded only for a transparent post-hoc sensitivity, P becomes 167 economies, the mean becomes **+0.5479066916**, and its difference from the unchanged 153-country baseline falls to **+0.0061712701** log-pp/year. The same identity then decomposes this gap into **−0.0329628842** composition and **+0.0391341543** within-region terms. This illustrates strong influence; it **does not prove errors or justify excluding CAF/DJI**.

## Reproducibility and scientific restrictions

- Reproduction code: `analysis/ae_2026_001_regional_cohort_mean_decomposition.py` (Python standard library, exact SHA256 lock, 217/153/16 count gates, algebraic identity check). GitHub workflow: `.github/workflows/ae-2026-001-regional-cohort-decomposition.yml`. Do not claim a successful GitHub Actions run or artifact unless independently observed.
- Only **2019–2023 current-release endpoint observations** were used; no historical 2024/2025 ILOSTAT vintages, independent employment source or countryatlas numerical benchmark.
- Sample selection is nonrandom; the equal-country mean is not global worker-weighted or population-weighted growth. No sampling standard errors, causal mechanisms, confirmatory hypothesis test, preregistration or methodological priority claim.
- The prior C15 153/169 medians and high-leverage checks remain valid; the current exercise decomposes **means**, not medians, and is a separate post-hoc sensitivity.
- Human author scientific review, actual originality and journal submission gates remain open. **MAJOR REVISION / NO SUBMISSION**.

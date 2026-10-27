# AE-2026-001 C34 — 2000–2019 regional post-stratification and unidentified missing-endpoint sensitivity

**27 October 2026.** Original, deterministic secondary reanalysis of a previously committed 2026-only WDI observed-country panel. **Not** a new vintage, imputation, global estimate, causal mechanism or publication novelty.

## Input, estimand, and integrity
Input: [source-locked 2026 WDI CSV](AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv), Git blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`; previously recorded source-file SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`. Direct calculation on **217** nonaggregate economy records, with **157** positive 2000/2019 pairs and **153** positive 2000/2019/2023 triples, consistent with earlier C13/C14/C33. These are **not** the primary 155-country 2024/2025/2026 three-vintage fixed cohort.

Define `g_i=100 ln(P_i,2019/P_i,2000)/19` log-percentage points per year. For each WDI metadata region r, let `N_r` be all 217-frame records, `n_r` observed 2000/2019 pairs, and `m_r` their observed mean. The hypothetical region-post-stratified value is `sum_r (N_r/217)*m_r`. It requires the **unverified assumption** that unobserved 2000/2019 growth in each region would average the same as observed growth; this assumption is **not identified from the data**.

## New calculated regional cells

| Region | All N_r | Observed n_r | Observed mean log-pp/year | Frame share |
| --- | ---: | ---: | ---: | ---: |
| East Asia & Pacific | 37 | 22 | 1.909379 | 17.05% |
| Europe & Central Asia | 58 | 46 | 3.909506 | 26.73% |
| Latin America & Caribbean | 42 | 28 | 1.620749 | 19.35% |
| Middle East, North Africa, Afghanistan & Pakistan | 23 | 17 | 2.092531 | 10.60% |
| North America | 3 | 1 | 2.765573 | 1.38% |
| South Asia | 6 | 6 | 2.684464 | 2.76% |
| Sub-Saharan Africa | 48 | 37 | 1.483629 | 22.12% |
| **Total** | **217** | **157** | **2.398498** (observed equal-economy mean) | **100%** |

## Numerical results and counterfactual missingness sensitivity

- Observed 157-economy 2000–2019 mean: **2.398498365** log-pp/year.
- Hypothetical 217-frame region-post-stratified mean: **2.346616320** log-pp/year, a difference of **-0.051882045** from the observed 157-country mean.
- Separate 153-economy three-endpoint subset: observed 2000–2019 mean **2.402070624**, region-post-stratified value **2.350067134** log-pp/year (same 217-frame region weights). This does not change the primary 155-economy historical-vintage result.
- North America has **only 1/3** eligible 2000/2019 records. Its observed region mean cannot identify growth of its two missing records.

For the 60 records without an eligible 2000/2019 pair, let `m_miss` denote a **hypothetical** mean growth rate if valid endpoints had been available. The counterfactual full-frame mean would be `(157*2.3984983654433942+60*m_miss)/217`:

| Assumed missing-group mean, log-pp/year | Counterfactual 217-frame mean, log-pp/year |
| ---: | ---: |
| -5 | 0.352831 |
| -2 | 1.182324 |
| 0 | 1.735319 |
| 2 | 2.288314 |
| 5 | 3.117808 |

The counterfactual full-frame mean changes sign only if `m_miss < -6.276071` log-pp/year. This is an algebraic **tipping point**, not an estimate of missing growth or a forecast. A small observed region-reweighting shift **does not** establish missing-at-random or representativeness.

## Exact replication procedure
Read the CSV with a quote-aware parser, trim `region`, require strictly positive finite values in the 2000 and 2019 columns, compute `100*Math.log(y2019/y2000)/19`, group by region, calculate observed means and `sum(N_r/217*mean_r)`. Assert `N=217`, `n=157`, `n3=153`. This analysis was executed against the complete source CSV through the GitHub connector, without new API download, imputation or external computation charges.

## Adversarial AI assessment
The 60 missing growth rates are unobserved, and the seven coarse regions do not control within-region selection. Region standardization is only an assumption-dependent descriptive sensitivity, not an estimator of world agricultural productivity. Equal-country weighting is not population-, worker- or output-weighted. This does not resolve archived ILOSTAT component vintages, shared-source dependence, exact countryatlas three-vintage numerical benchmark or novelty. **MAJOR REVISION / NO SUBMISSION.**

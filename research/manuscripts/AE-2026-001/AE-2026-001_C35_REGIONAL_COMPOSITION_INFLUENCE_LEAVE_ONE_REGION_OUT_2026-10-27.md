# AE-2026-001 C35 — exact regional composition decomposition and leave-one-region-out sensitivity

**27 October 2026. New deterministic reanalysis of the previously committed 2026-only WDI country panel.** Not a new source vintage, a global estimate, a missing-data correction, a novel estimator or independent empirical validation.

## Source and strict replication gate
- Repository input: `research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`; Git blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`; previously recorded file SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`. The blob was fetched afresh for this calculation.
- Parse the quoted CSV; trim WDI region strings; keep only strictly positive 2000 and 2019 indicator endpoints. Annualized log growth `g_i=100*ln(P2019/P2000)/19`.
- Assert 217 nonaggregate records, 157 observed endpoint pairs, seven WDI regions, observed mean `2.398498365443394` and C34 hypothetical region-weighted mean `2.3466163200902206`. These assertions passed.
- **Distinct estimand:** this is a 2026-only 157-economy selection sensitivity; the main 155-economy 2024/2025/2026 vintage comparison is unchanged.

## Exact decomposition and region exclusion
Let `N_r` be the count of all frame economies in region r, `n_r` the observed count and `m_r` the observed mean. The C34 hypothetical adjustment is **exactly**
`D = sum_r (N_r/217 - n_r/157) * m_r = -0.0518820453531732` log-pp/year.

For each omitted region k, recompute the observed mean and hypothetical frame-weighted mean **among the remaining six regions**, renormalizing both denominators. The difference is `D_{-k}`. These are influence diagnostics with **changed target frames**, not seven independent world estimates.

| WDI region | Frame N | Observed n | Observed mean g | Contribution to full-frame D | Six-region D after excluding this region |
| --- | ---: | ---: | ---: | ---: | ---: |
| East Asia & Pacific | 37 | 22 | 1.909379 | 0.058006 | -0.041714 |
| Europe & Central Asia | 58 | 46 | 3.909506 | -0.100523 | 0.004191 |
| Latin America & Caribbean | 42 | 28 | 1.620749 | 0.024643 | -0.046488 |
| Middle East, North Africa, Afghanistan & Pakistan | 23 | 17 | 2.092531 | -0.004791 | -0.058912 |
| North America | 3 | 1 | 2.765573 | 0.020619 | -0.055402 |
| South Asia | 6 | 6 | 2.684464 | -0.028366 | -0.050126 |
| Sub-Saharan Africa | 48 | 37 | 1.483629 | -0.021469 | -0.088858 |
| **All seven regions** | **217** | **157** | **2.398498** (overall observed mean) | **-0.051882** | **not applicable** |

## New finding and limitations
The Europe & Central Asia composition term is **-0.100523** log-pp/year, more negative than the net seven-region adjustment, while East Asia & Pacific contributes **+0.058006**. **Removing Europe & Central Asia reverses the adjustment sign to +0.004191**; removing Sub-Saharan Africa makes it **-0.088858**. Thus even the small C34 hypothetical regional adjustment is composition-sensitive and should **not** be used as evidence that missing observations are innocuous.

The regional contribution terms are a **descriptive accounting identity**, not causal attribution. The 60 unobserved endpoint-pair growth rates remain unidentified; North America has only 1/3 observed pairs, and South Asia has 6/6. Equal-economy weighting is not population-, employment-, production- or farm-weighted. No missing-data mechanism is estimated. No countryatlas three-vintage numerical benchmark or archived ILOSTAT employment source is obtained here.

**Internal AI adversarial verdict:** useful sensitivity of an existing hypothetical calculation; no novelty or publication-stage transition. **MAJOR REVISION / NO SUBMISSION.**

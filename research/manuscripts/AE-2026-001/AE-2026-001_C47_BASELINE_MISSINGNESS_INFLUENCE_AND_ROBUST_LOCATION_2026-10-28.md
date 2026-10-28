# AE-2026-001 C47 — Baseline-missingness outlier influence and robust-location sensitivity

**28 October 2026 | Internal, descriptive, source-locked computation | MAJOR REVISION / NO SUBMISSION**

## Data and executed computation
Source: `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`, Git blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`, previously recorded file SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`. Direct JavaScript calculation on the **complete fetched CSV** in this cycle; companion Python reproduction source committed as `analysis/c47_baseline_missingness_outlier_influence.py`, **not claimed to have been executed by GitHub Actions**.

Use `g_i=100 ln(P_i,2023/P_i,2019)/4` (annual log-percentage points) for positive finite endpoints. The 217-row WDI 2026 snapshot has 169 valid 2019/2023 pairs; 153 have positive 2000 baseline (B), and 16 lack it (M). No imputation, statistical significance, causal explanation, historical-vintage identity, or independent worker measurement is inferred.

## New influence diagnostics beyond C45/C46
- Overall arithmetic mean, 169 cases: **0.810142320409**; baseline-observed mean, 153: **0.541735421491**; difference **+0.268406898918** log-pp/year (previously established C45).
- Newly calculated 10% two-sided trimmed means: **0.924775426840** (169; trim 16 at each tail) versus **0.849039268047** (153; trim 15 at each tail), difference **+0.075736158792**.
- Newly calculated 20% trimmed means: **0.985322939010** (169; trim 33 each tail) versus **0.893466894923** (153; trim 30 each tail), difference **+0.091856044086**.
- Previously reported median difference is **+0.084670931687**, consistent with a much smaller robust-location contrast than the raw mean difference. The trimmed comparisons are **descriptive estimand changes**, not corrections to the mean and not evidence that missingness is ignorable.
- **CAF (Central African Republic)** has `g=+28.153795057491` and contributes **+0.163384968260** to the original 169-denominator accounting difference, **60.87%** of the full +0.268406899 shift. Removing CAF from the 169-case group and recomputing its 168-case mean reduces the shift relative to the unchanged 153-case B mean to **+0.105647061197**. These two quantities differ because the leave-one-out denominator changes.
- **DJI (Djibouti)** has `g=+17.259839592493`, fixed-frame contribution **+0.098923693320**; its deletion produces shift **+0.170492034203**.
- The largest negative fixed-frame contribution is **SLB (Solomon Islands)**, `g=-7.376068614637`, contribution **-0.046850911456**; deleting it produces shift **+0.317134344960**.
- The 16 fixed-frame contributions `(g_i - mean_B)/169` sum to **+0.268406898918**. They are accounting contributions **not causal country effects**; the leave-one-out recomputation is separate.

## Critical scientific interpretation
The 169-vs-153 mean contrast is highly sensitive to a small number of baseline-missing economies, particularly CAF. Reporting only the mean would overstate stability. The trimmed-mean and median shifts remain positive but are far smaller; they do **not** validate a general population claim because the 48 other economies lacking 2019/2023 endpoints remain unidentified. Extreme growth rates could reflect source revision, small denominator, real economic changes or other mechanisms; none was investigated here. Do not label these data an ILOSTAT vintage test, a causal treatment effect, or a novel estimator.

## Reproducibility and release gate
Run the companion Python script only against the exact source CSV; it fails closed on SHA256 or 217/169/153/16 frame mismatch and prints all 16 influence records. The Python script was committed but **not executed in this cycle**. Numerical results above were independently calculated directly in JavaScript from the fetched GitHub CSV. Full historical WDI 2024/2025 source identity, ILOSTAT vintage and same-source limitations, direct countryatlas comparator, author sign-off and journal suitability remain unresolved.

**Decision: maintain MAJOR REVISION / NO SUBMISSION.**

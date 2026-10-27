# AE-2026-001 C30 — Baseline-availability selection in 2019 productivity levels and absolute annualized endpoint-growth magnitude

**Terminology correction (27 October):** The file path retains the legacy word 'VOLATILITY', but only 2019 and 2023 endpoints were observed. Absolute annualized growth is **not** a time-series volatility estimator; see [C31](AE-2026-001_C31_OUTLIER_EXCLUSION_AND_REGION_STRATIFIED_ABSOLUTE_GROWTH_SELECTION_2026-10-27.md). No original data or numeric result was changed.\n\n**27 October 2026.** Original secondary descriptive computations from the already committed, official, dated 2026 WDI country panel. This is **not** an additional historical WDI vintage, an independently generated employment dataset, a new estimator, a causal result or proof of journal novelty.

## Exact source and cohorts

[Official WDI observed-country panel](AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv), GitHub blob SHA **d4910ff78219f9e5097c6301a6fbfa7752bbf4f9**; 217 nonaggregate economy rows. Variables: `NV.AGR.EMPL.KD` at 2000, 2019 and 2023, constant 2015 US dollars per worker. All 169 countries with positive finite 2019 and 2023 values were classified **without imputing missing 2000**: 153 have a positive 2000 baseline (`111`), while 16 lack a valid 2000 baseline (`011`). The exact availability census is independently documented in [C14](AE-2026-001_C14_THREE_ENDPOINT_AVAILABILITY_MASK_CENSUS_2026-10-26.md). This is **not** the separate primary 155-economy three-vintage fixed cohort.

## Question 1: Is 2019 observed productivity distributed differently among economies without a 2000 baseline?

- Median 2019 productivity, 153 complete three-date economies: **$6,237.918811** per worker.
- Median 2019 productivity, 16 economies lacking a valid 2000 baseline: **$2,840.965385** per worker.
- Mean natural-log 2019 productivity: **8.823396** versus **8.094420**, respectively; these are log units, not dollars.
- The exact cross-group pairwise probability that a randomly selected observed member of the 16 has a **higher** 2019 productivity level than an observed member of the 153 is **868/2448 = 0.354575** (there were no ties in this computation). Corresponding descriptive Cliff delta = **−0.290850**. This is a finite-sample rank contrast, not a population probability estimate.

**Regional composition sensitivity.** Of the 16 baseline-missing cases, 7 are Sub-Saharan African, 5 MENA/Afghanistan/Pakistan, 2 European/Central Asian and 2 East Asian/Pacific; none are in the other three WDI regions. Within-region pairwise probabilities (baseline-missing economy above a baseline-present economy's 2019 level) were **0.559524** in Sub-Saharan Africa (7×36 comparisons), **0.280000** in MENA (5×15), **0.144444** in Europe/Central Asia (2×45) and **0.363636** in East Asia/Pacific (2×22). Pooling all **461 within-region** cross-group comparisons yields **191/461 = 0.414317**. The pooled cross-region 0.354575 contrast is therefore sensitive to region composition, and the direction is reversed within Sub-Saharan Africa. Do not assert a common country-level missingness mechanism or call the difference statistically significant.

## Question 2: Does baseline availability select a different observed 2019–2023 absolute annualized 2019–2023 endpoint-growth distribution?

For each of the 169 economies compute `g=100*ln(P2023/P2019)/4` annual log-percentage points and summarize **absolute** g separately by 2000-baseline availability.

| Descriptive statistic | 153 baseline-present | 16 baseline-missing |
| --- | ---: | ---: |
| Median signed annual growth, log-pp/year | +0.890440 | +2.673188 |
| Median absolute annual growth, log-pp/year | **2.316370** | **4.759665** |
| Mean absolute annual growth, log-pp/year | 3.772972 | 6.406042 |
| Absolute annual growth >5 log-pp/year | 40/153 | 7/16 |
| Absolute annual growth >10 log-pp/year | 9/153 | 2/16 |
| Absolute annual growth >15 log-pp/year | 1/153 | 2/16 |

The two baseline-missing economies exceeding 10 log-pp/year in absolute magnitude are **CAF (+28.153795)** and **DJI (+17.259840)**. Their outlier influence on the *signed mean* was already established in C19 and **is not claimed as a new discovery here**. The new result is the baseline-availability **absolute-growth distribution** and its contrast with the 153 complete cases. Because the baseline-missing cohort is small and selected, neither ratio is a causal or population-representative effect.

## Reproducible calculation

Parse the source CSV with quoted fields. For each row define `valid(y) = finite(y) && y>0`. Retain `valid(P2019) && valid(P2023)`. Split on `valid(P2000)`. Calculate medians as the central order statistic (or average of the two central values for even n), log means and pairwise rank comparisons for P2019; separately calculate absolute annual log growth, threshold counts and country identities. All 153+16=169 retained records and 16×153=2448 cross-group comparisons are enumerated. Regional pairwise comparisons use only pairs sharing the exact WDI region string after trimming whitespace. No bootstrap, hypothesis test, imputation, historical revision attribution or extra data access was performed.

## Adversarial scientific interpretation and manuscript release gate

1. Missing 2000 observations may reflect reporting/coverage, not a known selection process; the data cannot identify why a country's 2000 value is missing.
2. Country regions differ in productivity levels; within-region and pooled rank contrasts differ substantially. There are only 2 baseline-missing cases in two of the four eligible regions.
3. The 2019 level is also the denominator of 2019–2023 growth; baseline-level/growth association is susceptible to mathematical coupling. Do not infer a causal pathway from missingness to growth.
4. This is a **2026-only** selection diagnostic. It neither changes the 155-economy **2024/2025/2026 historical vintage** estimand nor resolves archived ILOSTAT 2024/2025, countryatlas three-vintage benchmark, employment-source non-independence or novel scientific contribution.
5. The manuscript may use these findings to qualify selection/coverage and the absolute magnitude of annualized 2019–2023 net endpoint growth in a differently selected cohort. Two endpoints do **not** measure within-period time-series volatility. **MAJOR REVISION / NO SUBMISSION**; human author approval remains necessary.

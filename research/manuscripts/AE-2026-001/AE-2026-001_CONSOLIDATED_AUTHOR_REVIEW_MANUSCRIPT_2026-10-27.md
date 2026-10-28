# Historical Release Revisions in Agricultural Value Added per Worker: A Fixed-Country Audit of Three World Development Indicators Vintages

**Status:** consolidated **internal author-review manuscript**, 27 October 2026; not scientifically final, not author approved, not submitted, not peer reviewed. The proposed human author must verify and materially contribute to the final text. This is a compact, transparent synthesis of existing source-locked analyses, **not a new empirical dataset or an additional independent finding**.

## Abstract

**Purpose.** To quantify how historical data releases alter country-level agricultural value-added-per-worker growth estimates and to distinguish such revisions from changes in observation horizon and employment-source coverage. **Data and methods.** We compared archived October 2024 and October 2025 World Development Indicators (WDI) Excel releases with a dated October 2026 official WDI snapshot. We fixed the 2000–2019 country sample to the 155 economies with positive observations in all three releases, computed annualized logarithmic growth and paired release revisions, and inspected sign, magnitude and rank sensitivity. A separately retrieved current ILOSTAT employment file and a WDI value-added numerator provided a limited denominator-consistency check. **Results.** Median 2000–2019 annualized log growth across the same 155 economies was 2.6561, 2.6969 and 2.3617 log-percentage points per year in the 2024, 2025 and 2026 releases. Growth signs changed in six, six and ten economies in the respective 2024→2025, 2025→2026 and 2024→2026 comparisons. The 2024→2026 Spearman country-ranking correlation was 0.8870; 26/155 economies had an absolute growth-rate revision exceeding one log-percentage point annually. A current-source ILOSTAT versus WDI-implied worker-level comparison yielded 200 matched country-year observations across 127 economies, with median absolute relative difference 5.805%; this is not an independent employment validation because WDI cites ILOSTAT. A separate 153-economy 2026-only three-date cohort showed that the overlapping 2000–2023 horizon mechanically attenuates the 2019–2023 versus 2000–2019 rate contrast by 4/23. **Conclusions.** Release date, country selection and growth-rate convention materially affect descriptive cross-country results. The evidence does not identify why statistical agencies revised the series, establish global causal productivity trends, or demonstrate a novel estimator.

**Keywords:** agricultural labor productivity; World Development Indicators; data vintage; reproducibility; ILOSTAT; country selection.

## 1. Introduction

Agricultural value added per worker is a convenient indicator of aggregate sectoral output per employed person, but it is not farm yield, hours-adjusted productivity or total factor productivity. Sectoral national accounts and employment estimation introduce definition, coverage and revision uncertainty. The WDI series NV.AGR.EMPL.KD includes agriculture, forestry and fishing, and draws on World Bank national accounts and ILOSTAT. Published country-level growth can therefore vary when source series are revised even if the reference period stays unchanged.

Existing literature establishes agricultural productivity gaps and the importance of structural heterogeneity (Gutierrez, 2002; Eberhardt and Teal, 2013; Gollin, Lagakos and Waugh, 2013/2014; Dieppe and Matsuoka, 2021/2025). Research on economic database revisions likewise predates this study (Johnson et al., 2013; Filer et al., 2004). Our contribution is deliberately **narrow**: an auditable descriptive comparison of specific archived WDI releases for a fixed set of economies. We do not claim priority for a vintage-comparison method or the first demonstration of revision sensitivity.

The questions are: How much do annualized 2000–2019 country growth estimates change across the October 2024, October 2025 and October 2026 releases? How robust are sign and rank classifications to these revisions? What is and is not learned from comparing the published per-worker indicator with a separately retrieved current ILOSTAT employment file? How can one prevent release revision from being confused with changing observation horizons?

## 2. Data and methods

### 2.1 Sources and fixed cohort

The primary series is WDI **NV.AGR.EMPL.KD**, agriculture, forestry and fishing, value added per worker (constant 2015 US$). Two original WDI archive ZIPs were dated **24 October 2024** (78,163,670 bytes; SHA256 `5a8922c6629eea69b93a314ebb2363ed8d5faf4f345ff19dbe203c62692af5a1`) and **8 October 2025** (81,022,548 bytes; SHA256 `9185df6f3029ca6c990d87674dcec60e4633cf0b344bc4ee6459392f1cfdc173`). The 2026 comparison uses the previously archived official API extract, whose source update was labelled **8 October 2026**, and not a rolling current API response. The country panel is version-controlled as `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`, blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`, source-file SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`.

**Primary archive link provenance (C43, 28 October 2026).** The World Bank's [official WDI Archives index](https://datatopics.worldbank.org/world-development-indicators/wdi-archives.html) links directly to [the 24 October 2024 Excel archive](https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_excel_2024_10_24.zip), [the 8 October 2025 Excel archive](https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_excel_2025_10_08.zip), and [the 8 October 2026 Excel archive](https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_EXCEL_2026_10_08.zip). The link dates match the manuscript's recorded release labels. These are source-identification links only: the 2026 Excel ZIP is **not** the source-locked 2026 API CSV, and byte-equivalence or source-57 API archive identity was **not** established by this index check. Original 2024/2025 ZIP hashes are historical CI evidence and were not recalculated in C43. See [C43 provenance note](AE-2026-001_C43_OFFICIAL_WDI_OCTOBER_ARCHIVE_URL_CROSSWALK_AND_IDENTITY_GATE_2026-10-28.md).

We exclude aggregate series using WDI country metadata and require positive finite 2000 and 2019 values in **all three releases**, producing the same **155 economies** in every primary comparison. This complete-case design prevents changing country composition from being mistaken for a release effect **within this selected sample**, but cannot eliminate selection bias. All economies have equal analytical weight. We do not impute absent values.

### 2.2 Primary outcomes and revisions

For economy i and vintage v, annualized log growth is `g_iv = 100[ln(P_i,2019,v)−ln(P_i,2000,v)]/19` log-percentage points/year. Paired release revision is `Δg_i(v→w)=g_iw−g_iv`. We report vintage-specific medians, median paired revisions, median absolute paired revisions, growth-sign switches and Spearman ranking correlations. **The median of paired revisions is not the difference of vintage medians.** Exploratory robustness requires absolute growth rates on both sides of a sign change to exceed post hoc thresholds of 0.1, 0.2, 0.5 or 1.0 log-percentage points annually. These thresholds are not statistical significance criteria.

The original 2024 WDI archive used here contains **no eligible 2023 endpoint** for this indicator; hence a 2000–2023 *three-vintage* analysis is not identified and is not imputed.

### 2.3 Current-source worker-level comparison

For a separate, strictly qualified source-consistency check, we use the official ILOSTAT `EMP_TEMP_SEX_ECO_NB_A` RDS with total sex, broad agricultural aggregate and best-source records at 2000/2019. We obtain the WDI agricultural value-added numerator `NV.AGR.TOTL.KD` from its separately retrieved 2026 API source, and derive the algebraic WDI-implied worker count `L*=V/P`. The ILOSTAT count is converted from thousands of workers to persons before comparison. **The two downloaded files are separately retrieved but not necessarily independently generated**: WDI explicitly lists ILOSTAT among the sources underlying the published per-worker indicator. These checks do not reconstruct 2024 or 2025 ILOSTAT employment vintages or attribute historical revisions to numerator versus denominator.

### 2.4 Distinguishing horizon from release

As a separate **2026-only** sensitivity, 153 economies have positive values at 2000, 2019 and 2023. Let E, L and H denote annual log-percentage-point growth for 2000–2019, 2019–2023 and 2000–2023. The exact identity `23H=19E+4L` implies `H−E=(4/23)(L−E)` for each economy. This comparison uses **153** three-endpoint cases and must not be conflated with the primary **155** historical-vintage cases. We also checked the documented compound annual growth rate (CAGR) convention using the actual `countryatlas::growth_rate(type="cagr")` R package (countryatlas 3.0.0), but **did not** execute a historical three-vintage `countryatlas::compare_vintages` head-to-head.

**Comparator estimand and release-identity gate (C32).** Current countryatlas documentation specifies that `compare_vintages(indicator, vintages, year, countries)` compares **one reference year's indicator levels** across WDI archive releases; it does not directly return the **2000–2019 annualized log-growth revision** estimated here. A valid external implementation therefore requires separate **year=2000 and year=2019** comparisons, a country-and-vintage join, the identical 155-economy positive-endpoint restriction, and recomputation of the logarithmic growth contrast. Archive ZIP timestamps must also be reconciled with actual `wdi_vintages()` API release labels and constant-price units before numerical equality can be asserted. The current package website's release-list example is not a live availability check. This required exact-release comparison **has not been executed or validated**; the earlier direct `growth_rate(type='cagr')` execution tests a different estimand. See [C32](AE-2026-001_C32_COUNTRYATLAS_COMPARE_VINTAGES_ESTIMAND_AND_RELEASE_IDENTITY_GATE_2026-10-27.md).

### 2.5 Reproducibility and inference

**Additional source-identity and software-version qualification (C39).** The published countryatlas documentation identifies the WDI archive endpoint as **World Bank API source 57**, with API release identifiers such as `202510` for "2025 Oct"; such labels are **not byte-level identities** for the local 8 October 2025 or 24 October 2024 WDI ZIP files. The documentation's example lists a 2026-07 archive, which is **not** interchangeable with the rolling October 2026 `current` extraction. Moreover, the currently rendered documentation is for countryatlas **4.0.0**, while the earlier project CAGR execution used **3.0.0**; no cross-version numerical equality is assumed. The required benchmark must separately retrieve 2000 and 2019 endpoints for matching releases, join the same 155 economies, check units, and recompute growth. This is a methodological gate, not a completed countryatlas benchmark. See [C39](AE-2026-001_C39_COUNTRYATLAS_SOURCE57_RELEASE_IDENTITY_AND_YEAR_MATCH_GATE_2026-10-27.md) and https://pursuitofdatascience.github.io/countryatlas/reference/wdi_vintages.html .

**Additional upstream archive-client provenance gate (C40).** Inspection of the current countryatlas upstream source (4.0.0 documentation/code, **not** an executed 3.0.0 archive benchmark) shows that archived WDI source-57 requests use explicit `version/YYYYMM` and `time/YR2000;YR2019` parameters, rather than the rolling WDI endpoint's year-range syntax. The upstream client also canonicalizes legacy country codes (including WBG→PSE, ZAR→COD and ROM→ROU) and resolves duplicate country-year keys. These implementation details make raw-to-canonical country mapping and duplicate resolution additional audit requirements for a source-locked 155-economy comparison; there is **no evidence yet** that a specific alias changed this study's numerical results. The direct three-vintage API comparison, exact historical ZIP equivalence and independently verified 155-country cohort input remain uncompleted. See [C40](AE-2026-001_C40_COUNTRYATLAS_ARCHIVE_ENDPOINT_LEGACY_ISO_COLLISION_AND_FIXED_COHORT_GATE_2026-10-27.md).


**Executed 2026-only canonical ISO diagnostic (C41, 27 October 2026).** Direct parsing of the source-locked 217-row 2026 WDI panel found 217 unique ISO3 keys, no duplicate keys, no occurrences of six historical aliases (ADO/ZAR/TMP/ROM/KSV/WBG), and all six canonical counterparts (AND/COD/TLS/ROU/XKX/PSE); four of those six had positive 2000 and 2019 endpoints. This is a **narrow validation of the 2026-only panel**, not proof that historical 2024/2025 source-57 archives or the 155-country three-vintage sample are alias-free. The direct archive comparator and release-identity gate remain open. See [C41](AE-2026-001_C41_2026_PANEL_LEGACY_ISO_CANONICAL_COVERAGE_2026-10-27.md).

**C42 source-identity benchmark implementation correction (27 October 2026).** The original countryatlas benchmark draft incorrectly made a third historical API-vintage label (presumed `2026-10`) a mandatory input, even though the study's third source is a **separately archived October 2026 WDI CSV snapshot**. A new [two-historical-API-release plus SHA256-locked 2026 snapshot comparator](analysis/countryatlas_two_archive_plus_locked_2026_snapshot_benchmark.R) now specifies explicit 2000/2019 endpoints, the independently verified 155-country cohort and strict source integrity. This is **prepared code, not an executed benchmark**: the 155-country input, API release availability and historical ZIP-to-API equivalence still require evidence. See [C42](AE-2026-001_C42_COUNTRYATLAS_TWO_HISTORICAL_RELEASES_PLUS_SOURCE_LOCKED_2026_BENCHMARK_GATE_2026-10-27.md). No numerical equivalence or novelty is inferred.

Original source-hashed three-vintage calculation: `analysis/wdi_three_vintage_fixed_cohort_revisions.py`, GitHub Actions run **40241769129**, artifact **12616508530**. Original sign-margin audit: run **40251337787**, artifact **12620841635**. Ranking audit: run **40260737559**, artifact **12623633345**. Current-source worker audit: run **40300738631**, artifact **12640371610**. The direct countryatlas CAGR implementation: run **40407883759**, artifact **12692315824**. The 2026-only exact horizon identity and row-level checks are documented in C26. These are computational provenance records, **not** independent peer review. Analyses were post hoc and descriptive. No design-based confidence interval for the global agricultural sector is asserted.

### 2.6 Exploratory sign-switch margin sensitivity (C27)

As an additional post hoc diagnostic within the **153-economy 2026-only cohort**, we compared strict growth-rate sign reversals between E and L (nonoverlapping periods) and between E and H (overlapping horizons). For margins m = 0, 0.1, 0.2, 0.5, 1 and 2 annual log-percentage points, a reversal is retained only if both compared rates have absolute magnitude greater than m. The identity 23H=19E+4L implies that, for E and L of opposite signs, a strict E-to-H reversal requires |L|>4.75|E|. These exploratory margins are **not** tests of statistical significance or a new estimator.

### 2.7 Exploratory baseline-productivity stratification (C28)

To assess whether the separate 2026-only 2000–2019 versus 2019–2023 period contrast is homogeneous across starting productivity levels, we sorted the 153 complete-case economies by year-2000 value added per worker and assigned quartiles by sorted row index `1+floor(4i/153)` for zero-based `i`. We summarized the paired country difference `d=L−E` in each quartile and calculated the descriptive Spearman correlation of log baseline productivity with d. This post hoc exercise uses the **153-economy 2026-only cohort**, not the primary 155-economy three-vintage cohort. Because the baseline value also enters E, mathematical coupling and regression to the mean preclude a causal interpretation.

### 2.8 Selection by availability of the 2000 baseline (C30)

A separate **2026-only** availability-selection diagnostic compared the **153** economies observed in 2000/2019/2023 with **16** additional economies observed in 2019/2023 but not at the positive 2000 baseline. We compared the distributions of observed 2019 productivity using medians and exact cross-group pairwise ranks; region-conditioned comparisons used only pairs from the same WDI region. Independently, we compared the distributions of **absolute** 2019–2023 annualized log growth, `|100 ln(P2023/P2019)/4|`, using medians and **post hoc** descriptive thresholds 5, 10 and 15 log-percentage points. These are post hoc finite-sample descriptions, not tests of a missing-data mechanism, and must not be conflated with the primary 155-economy **three-vintage** analysis. Calculations and country identities are documented in [C30](AE-2026-001_C30_2000_BASELINE_MISSINGNESS_2019_LEVEL_AND_VOLATILITY_SELECTION_2026-10-27.md).

### 2.9 Region-stratified endpoint availability (C33)

We re-tabulated the previously committed **217-economy 2026-only** observed-country CSV by its exact WDI metadata region. A year was available only when the indicator value was finite and strictly positive; the chronological 2000/2019/2023 availability mask was counted without imputation. We report each region's denominator, three-endpoint complete cases, two-endpoint 2019/2023 cases and other missingness masks. These are administrative availability fractions, **not** population-weighted coverage, tests of missingness mechanisms, or estimates of world agricultural output. This region census does **not** alter the separate **155-economy historical-vintage** cohort. Full counts and a standard-library replication recipe are provided in [C33](AE-2026-001_C33_REGIONAL_ENDPOINT_AVAILABILITY_SELECTION_2026-10-27.md).

### 2.10 Assumption-dependent 2000–2019 regional post-stratification (C34)

As an additional **2026-only** descriptive sensitivity, we computed observed annualized 2000–2019 log-growth means among the 157 economies with positive endpoints, then reweighted the seven observed WDI regional means using the region shares of all 217 nonaggregate economy records. This post-stratification is a **hypothetical** 217-frame calculation requiring untestable equality of observed and missing growth means within each region; it does **not** identify missing growth, impute data or estimate a global population/worker-weighted mean. A separate algebraic tipping-point calculation varies the assumed mean of the 60 missing-endpoint cases. This analysis is distinct from the **155-economy historical three-vintage** sample and from the 2019–2023 C16 cohort decomposition. See [C34](AE-2026-001_C34_REGION_POSTSTRATIFICATION_AND_UNIDENTIFIED_2000_2019_MISSING_GROWTH_2026-10-27.md).

### 2.11 Sharp finite-frame median bounds for unobserved growth (C36)

For the separate **2026-only** frame of 217 nonaggregate economy records, 157 have positive 2000 and 2019 productivity endpoints and 60 do not. We order the 157 observed annualized log-growth rates. Without imputing or restricting the 60 unobserved rates, the hypothetical 217-record median is the 109th order statistic and has the **sharp finite-frame bounds** given by the 49th and 109th observed rates. This is deterministic partial identification, not a confidence interval, a new estimator, or an inference about global worker-weighted productivity. See [C36](AE-2026-001_C36_SHARP_FINITE_FRAME_MEDIAN_MISSINGNESS_BOUNDS_2026-10-27.md).

### 2.12 Sharp prevalence bounds for growth-threshold classifications (C38)

For the **separate 2026-only 217-record frame**, we extended the missing-growth sensitivity from a median value to the fraction of economy/territory records exceeding a growth threshold. For a region with N records, n valid 2000/2019 endpoint pairs, m=N−n missing rates and k observed annualized log-growth rates strictly greater than a threshold t, unrestricted missing values imply sharp bounds `[k/N, (k+m)/N]`. We calculated these bounds for t=0,1,2,3,5 annual log-percentage points and for t=0 within each of the seven WDI metadata regions. These are deterministic finite-frame bounds, **not confidence intervals**, imputed values, prespecified hypotheses or population/worker-weighted global growth estimates. Reproducible source-locked calculation and regional counts: [C38](AE-2026-001_C38_SHARP_POSITIVE_GROWTH_PREVALENCE_BOUNDS_BY_REGION_2026-10-27.md).

### 2.13 Sharp finite-frame quantile identification limits (C44)

For the separate 2026-only frame of 217 economies, we extend the C36 order-statistic missingness analysis beyond the median. Define each p-quantile by the nearest-rank rule `k=ceil(217p)`. With 157 observed annualized 2000–2019 growth rates and 60 unrestricted missing rates, the sharp lower infimum is unbounded if `k<=60`, otherwise observed order statistic `x_(k-60)`; the upper supremum is unbounded if `k>157`, otherwise `x_(k)`. These are identification bounds, not uncertainty intervals or claims about actual missing-country growth. A source-SHA-locked Python replication is in [C44](AE-2026-001_C44_SHARP_FULL_FRAME_QUANTILE_MISSINGNESS_IDENTIFICATION_2026-10-28.md).

### 2.14 C45: full 2019–2023 cohort versus three-endpoint baseline selection

As a separate 2026-only descriptive selection check, we compared annualized 2019–2023 log growth `100 ln(P2023/P2019)/4` for all 169 economies with positive 2019/2023 observations against the 153 economies also observed at the 2000 baseline. The 16 additional cases are not assigned missing 2000 values. C30/C31 already evaluated baseline-availability group differences; the incremental C45 estimand is the **169-versus-153 signed-growth median difference**. Code and exact ISO3 membership are in [C45](AE-2026-001_C45_BASELINE_AVAILABILITY_SELECTION_2019_2023_2026-10-28.md). This is not the fixed 155-economy three-vintage sample.

## 3. Results

### 3.1 Primary fixed-country release sensitivity

**Table 1. Identical 155-economy 2000–2019 panel across three WDI releases**

| Statistic | October 2024 | October 2025 | October 2026 |
| --- | ---: | ---: | ---: |
| Median annualized log growth, log-pp/year | 2.656067 | 2.696920 | 2.361735 |
| Mean annualized log growth, log-pp/year | 2.606986 | 2.612402 | 2.433037 |

**Table 2. Paired revisions for the same 155 economies**

| Metric | 2024→2025 | 2025→2026 | 2024→2026 |
| --- | ---: | ---: | ---: |
| Median paired annual growth revision, log-pp/year | +0.007153 | −0.059085 | −0.111754 |
| Median absolute revision, log-pp/year | 0.166532 | 0.271055 | 0.412929 |
| Economies changing growth sign | 6 | 6 | 10 |
| Spearman country rank correlation | 0.9500 | 0.9189 | 0.8870 |
| Absolute annual growth revision >1 log-pp/year | 12 | 24 | 26 |

These are historical **published-estimate revisions**, not realized changes in agricultural performance over time. In the end-to-end comparison, the three largest absolute annual growth revisions were Singapore (−7.387 log-pp/year), Bahamas (+6.600) and Trinidad and Tobago (−5.796). The six plus six successive sign switches cannot be added to obtain net sign changes; Uganda switched in both successive transitions. In the 2024→2026 comparison, only **3/10** sign changes had absolute growth rates above **0.5 log-pp/year on both sides** (Bahamas, Timor-Leste, Trinidad and Tobago), showing the sensitivity of a binary sign classification near zero.

### 3.2 Measurement and selection limitations

The separately retrieved ILOSTAT source contained 617,241 original rows, but only 402 unambiguous country-year observations after the total-sex, broad-agriculture, best-source and endpoint filters. The worker-level comparison with the WDI-implied denominator yielded **200 positive matched country-year records across 127 economies**; the median absolute relative discrepancy was **5.8051%**, with **128/200** records within ±10%. For **73** economies with both 2000 and 2019 matched worker levels, the median absolute annual worker-growth discrepancy was **0.4104 log-pp/year** and **6/73** growth signs disagreed. This is a source-consistency diagnostic on a nonrandom subset, not evidence of an independent worker census or of the mechanism of historical WDI revisions.

The 2026 observed-country panel contains **217** nonaggregate economies. Its 2000/2019/2023 positive-availability masks were 43 `000`, 16 `011`, 1 `100`, 4 `110` and 153 `111`; all other masks were zero. The four `110` economies were Sudan, Syrian Arab Republic, West Bank and Gaza, and Ukraine. These masks describe missing observations, **not zero productivity**. The primary 155-economy historical-vintage cohort is a separate selection and is not reconstructed from these 153 cases.

### 3.3 Exact separation of horizon and release effects

Within the distinct **153-economy 2026-only** cohort, median annual growth was **2.355575** log-pp/year for 2000–2019, **0.890440** for 2019–2023 and **2.224484** for 2000–2023. The median within-country L−E contrast was **−1.925832** log-pp/year, versus **−0.334927** for H−E; the difference is exactly the algebraic factor **4/23**. The rowwise maximum floating-point residual was below 2×10⁻¹⁵ log-pp/year. **60/153** countries changed the sign of their growth rate from E to L, whereas **10/153** did so from E to H; the latter 10 are a subset of the former 60. The identical *number* 10 also appears in the separate 2024→2026 historical-vintage sign comparison, but the two counts have **different samples and causes**. None of these calculations demonstrates a structural break or causal post-2019 effect.

### 3.4 Growth-sign margin sensitivity within the 2026-only cohort

**Table 3. Exploratory growth-sign reversals under strict two-sided rate margins; 153 fully observed economies**

| Minimum absolute annual log growth on each compared side (log-pp/year) | E→L, nonoverlapping periods | E→H, overlapping horizons |
| ---: | ---: | ---: |
| 0 | 60 | 10 |
| 0.1 | 54 | 6 |
| 0.2 | 51 | 6 |
| 0.5 | 42 | 3 |
| 1.0 | 33 | 1 |
| 2.0 | 18 | 0 |

The ten overlapping-horizon sign reversals include seven with at least one rate no larger than 0.5 log-pp/year in absolute magnitude. This demonstrates the sensitivity of a binary growth-sign label to near-zero annual rates. It does not imply that the separate ten historical-vintage sign switches in the 155-economy primary analysis have the same identities or margins. Full country-level calculations and the exact 4.75 threshold are in [C27](AE-2026-001_C27_HORIZON_SIGN_SWITCH_MARGIN_ROBUSTNESS_2026-10-27.md). No uncertainty or causal inference is attached to these post hoc thresholds.

### 3.5 Exploratory heterogeneity by baseline agricultural productivity (C28)

**Table 4. Baseline year-2000 productivity quartiles in the separate 2026-only 153-economy period contrast**

| Baseline productivity quartile | Economies | Median paired change in annual log growth (log-pp/year) | Economies with lower growth in 2019–2023 |
| --- | ---: | ---: | ---: |
| Q1, lowest | 39 | −2.650990 | 31 |
| Q2 | 38 | −2.493042 | 29 |
| Q3 | 38 | −0.460747 | 24 |
| Q4, highest | 38 | −1.563035 | 25 |
| **Total** | **153** | **−1.925832 (pooled median)** | **109** |

The rank correlation between log baseline productivity and the paired change was **+0.133214**, descriptive only. All four quartile medians were negative, but the pattern was **not monotone**. These observations do not establish a productivity-convergence mechanism or a world-representative trend; quartile allocation and full source-locked calculations are documented in [C28](AE-2026-001_C28_BASELINE_PRODUCTIVITY_QUARTILE_PERIOD_CONTRAST_2026-10-27.md).

### 3.6 Baseline availability, observed productivity and absolute endpoint growth (C30/C31)

Among the **169** economies with positive 2019 and 2023 observations, the 153 with a positive 2000 baseline had median 2019 agricultural value added per worker of **$6,237.919**, compared with **$2,840.965** for the 16 lacking a valid 2000 baseline. In all 16×153 cross-group pairs, the proportion with the baseline-missing economy's 2019 value higher was **868/2448 = 0.3546**; however, this comparison mixes regions. Within the four regions containing baseline-missing economies, the pairwise proportion was **191/461 = 0.4143**, with a reversed direction in Sub-Saharan Africa (**0.5595**, 7 versus 36 economies). These observations caution against treating the 2000-complete cohort as a random subset of the 2019–2023-observed economies.

**Table 5. Descriptive 2019–2023 absolute annual log-growth by availability of the 2000 baseline (2026-only data)**

| Measure | 2000 baseline present | 2000 baseline missing |
| --- | ---: | ---: |
| Economies | 153 | 16 |
| Median absolute annual log growth, log-pp/year | **2.3164** | **4.7597** |
| Absolute annual log growth >5 log-pp/year | 40/153 | 7/16 |
| Absolute annual log growth >10 log-pp/year | 9/153 | 2/16 |
| Absolute annual log growth >15 log-pp/year | 1/153 | 2/16 |

The two baseline-missing cases above 10 log-pp/year are Central African Republic and Djibouti, whose signed mean influence was already documented in C19. The comparison concerns the **absolute magnitude of four-year annualized net endpoint growth**, not within-period volatility (which cannot be measured from only the two endpoints), nor a novel causal finding. The small 16-economy cohort, regional mix, nonrandom missingness and mechanical use of 2019 productivity in the growth denominator limit interpretation. These 169 cases are **not** the primary 155-economy historical-vintage panel.

### 3.7 Extreme-economy exclusion and region-conditioned absolute-growth rank sensitivity (C31)

To assess the influence of the two largest positive-growth observations in the 16-economy baseline-missing group, we performed a post hoc sensitivity analysis excluding **CAF** and **DJI** from that group only; neither observation is asserted to be erroneous. The median absolute annualized 2019–2023 log growth fell from **4.759665** (n=16) to **4.498140** (n=14), still above **2.316370** in the unchanged 153-economy complete-baseline group. In contrast, the missing-baseline group's **signed** median changed from **+2.673188** to **+0.808881** log-pp/year, now below the complete-baseline median of **+0.890440**. Thus the signed median comparison is substantially more sensitive to these two extremes.

An exact cross-group comparison of **absolute** growth magnitudes yielded **1,597/2,448 = 0.652369** winning pairs for the baseline-missing group; after removing CAF and DJI, **1,293/2,142 = 0.603641**. Restricting comparisons to pairs within the same WDI region reduced these fractions to **291/461 = 0.631236** and **241/410 = 0.587805**, respectively. In Sub-Saharan Africa alone the within-region fraction changed from **132/252 = 0.523810** to **96/216 = 0.444444** after excluding CAF, reversing the descriptive direction. These are observed finite-sample rank proportions, not inferential probabilities, causal effects, measures of intra-period volatility or evidence of historical-vintage revisions. Full country-level definitions, exclusion rules and denominators are recorded in [C31](AE-2026-001_C31_OUTLIER_EXCLUSION_AND_REGION_STRATIFIED_ABSOLUTE_GROWTH_SELECTION_2026-10-27.md).

### 3.8 Regional composition of the endpoint-complete cohort (C33)

**Table 6. Regional coverage of the 2026-only three-endpoint observed-country panel**

| WDI metadata region | Economy records | Complete 2000/2019/2023 | Complete-case share | 2019/2023 pairs |
| --- | ---: | ---: | ---: | ---: |
| Latin America & Caribbean | 42 | 28 | 66.67% | 28 |
| Middle East, North Africa, Afghanistan & Pakistan | 23 | 15 | 65.22% | 20 |
| Sub-Saharan Africa | 48 | 36 | 75.00% | 43 |
| Europe & Central Asia | 58 | 45 | 77.59% | 47 |
| East Asia & Pacific | 37 | 22 | 59.46% | 24 |
| South Asia | 6 | 6 | 100.00% | 6 |
| North America | 3 | 1 | 33.33% | 1 |
| **Total** | **217** | **153** | **70.51%** | **169** |

The 16 additional 2019/2023 observations lacking a 2000 baseline comprised seven Sub-Saharan African, five Middle Eastern/North African/Afghanistan/Pakistan, two European/Central Asian and two East Asian/Pacific economies. The remaining availability masks were 43 with no positive endpoint, four with only 2000/2019 and one with only 2000. In this source-locked CSV, Canada has all three positive endpoints while the United States and Bermuda have none for **this indicator**; this does not mean those economies lack agricultural output or other statistics, and it is not independently revalidated against a live API. Coverage heterogeneity is a **sample-selection warning**, not proof of a missingness mechanism or a global representativeness adjustment. The full five-mask regional census and source-file checksum appear in [C33](AE-2026-001_C33_REGIONAL_ENDPOINT_AVAILABILITY_SELECTION_2026-10-27.md).

### 3.9 Region-post-stratified 2000–2019 growth and nonidentification (C34)

In the 2026-only observed 2000/2019 sample, the equal-economy mean annual log growth was **2.398498** log-percentage points/year across **157** cases. Reweighting the seven observed regional means to the **217-record** WDI region composition gave a **hypothetical** value of **2.346616**, a change of **−0.051882** log-percentage points/year. The analogous observed and hypothetical values for the separate **153-case** three-endpoint sample were **2.402071** and **2.350067**. Crucially, these are not estimates of the 60 unobserved growth rates: for a hypothetical missing-case mean of −2, 0 or +2 log-percentage points/year, the counterfactual 217-case mean would be **1.182324**, **1.735319** or **2.288314**, respectively. Because the missing mean is not observed, the apparent small reweighting change cannot establish representativeness or a missing-at-random mechanism. Full regional cells and exact algebra are in [C34](AE-2026-001_C34_REGION_POSTSTRATIFICATION_AND_UNIDENTIFIED_2000_2019_MISSING_GROWTH_2026-10-27.md).

### 3.10 Regional composition influence and exclusion sensitivity (C35)

A further **2026-only** decomposition of the hypothetical C34 adjustment gives the exact regional contributions `(N_r/217 - n_r/157)*mean(g_r)`. Europe & Central Asia contributes **−0.100523** log-percentage points/year and East Asia & Pacific **+0.058006**, against a net adjustment of **−0.051882**. Recomputing both means on the remaining six regions after omitting Europe & Central Asia reverses the adjustment to **+0.004191**; omitting Sub-Saharan Africa instead yields **−0.088858**. These are **changed-frame descriptive influence diagnostics**, not estimates of the missing 60 growth rates, tests of missing-at-random, or generalizable global productivity estimates. See [C35](AE-2026-001_C35_REGIONAL_COMPOSITION_INFLUENCE_LEAVE_ONE_REGION_OUT_2026-10-27.md).

### 3.11 Sharp missing-growth bounds for the 217-record median (C36)

The 157 observed 2000–2019 growth rates include **132 positive** and **25 negative** values. The observed median is **2.355575** log-percentage points/year. With all 60 missing rates unrestricted, the exact attainable interval for the hypothetical 217-record equal-economy median is **[1.423959, 3.689876]** log-percentage points/year (49th and 109th observed order statistics; boundary economies LBR and SWE). The median's **positive sign** is therefore robust to any finite values assigned to the 60 missing rates, although the median's **value** remains unidentified and the interval width is **2.265916** log-percentage points/year. This new median result is separate from C34's previously calculated **mean** tipping point, is **not** a novel estimator, and does not establish globally representative productivity growth. See [C36](AE-2026-001_C36_SHARP_FINITE_FRAME_MEDIAN_MISSINGNESS_BOUNDS_2026-10-27.md).

### 3.12 Partial identification of positive-growth prevalence and regional majority status (C38)

Of the **157** 2026-only observed 2000/2019 growth rates, **132** were strictly positive; **60** of the 217 frame records lacked valid endpoint pairs. The sharp fraction of all 217 records with positive growth is therefore **132/217 to 192/217 (60.83%–88.48%)**, establishing a positive-growth majority for this finite frame without identifying its exact prevalence. A majority above **1** annual log-percentage point is also robust (114/217=52.53% lower bound); a majority above **2** is not guaranteed (87/217=40.09% lower bound). The upper bound above **5** is only 79/217=36.41%, so even assigning every missing rate above 5 cannot yield a majority at that threshold.

Region-specific bounds qualify the aggregate result: a positive-growth majority is guaranteed in **five of seven** WDI metadata regions, but is **not identified** in East Asia & Pacific (14/37 to 29/37, 37.84%–78.38%) or North America (1/3 to 3/3, 33.33%–100%). These are equal-record, mixed country/territory comparisons, not globally representative or causally interpreted productivity trends. Full table and replication recipe: [C38](AE-2026-001_C38_SHARP_POSITIVE_GROWTH_PREVALENCE_BOUNDS_BY_REGION_2026-10-27.md).

### 3.13 Quantile-tail nonidentification in the 2026-only frame (C44)

For the 217-record nearest-rank quantiles, the 25th percentile (rank 55) is **unbounded below** and at most **1.629363** annual log-percentage points; the 75th percentile (rank 163) is at least **3.488990** and **unbounded above**. The 10th percentile is at most −0.064478 and unbounded below; the 90th is at least 4.838383 and unbounded above. The median remains bounded between **1.423959 and 3.689876**, reproducing C36. Thus the finite-frame interquartile spread is not point-identified by the 157 observed rates; observed-sample quartiles cannot be reported as all-217-frame quartiles. The unbounded limits express missing-data nonidentification, **not** observed extreme outcomes, a world productivity distribution or a novel statistical estimator.

### 3.14 C45: full two-endpoint frame changes the signed-growth median

In the 2026-only 2019–2023 data, the 169-economy median annualized signed log growth was **0.9751105** log-percentage points/year (101 positive, 68 negative). Requiring a positive 2000 baseline reduces this sample to 153 economies and gives median **0.8904395**, a difference of **+0.0846709** when the 16 late-baseline economies are included. The corresponding unweighted means are **0.8101423** and **0.5417354**. The 16 additional economies have median signed growth **2.6731881** and mean **3.3767833**; those subgroup figures are an independent replication of C31, **not new discoveries**. The comparison demonstrates an exact change in the selected estimand, not a missing-at-random test, causal effect or representative global trend.

## 4. Discussion
### 3.15 Regional accounting of the baseline-availability mean shift (C46)

A new exact decomposition of the **169-versus-153** 2019–2023 mean growth difference allocates the **+0.268407 annual log-percentage-point** shift to the 16 additional baseline-missing economies by their WDI metadata regions, relative to the overall 153-economy mean. The regional contributions are **Sub-Saharan Africa +0.146783**, **Middle East/North Africa/Afghanistan/Pakistan +0.145936**, **Europe/Central Asia +0.051301**, and **East Asia/Pacific −0.075613**; the remaining regions have no added cases and zero contribution. These terms sum to +0.268407 (floating-point tolerance). This is an additive *descriptive accounting identity*, not a causal region effect, equal-region standardization, or a new estimator. The mean shift is not interchangeable with the previously reported median shift of +0.084671. The 2026-only 169/153 comparison must remain distinct from the 155-economy historical-vintage panel. See the source-locked calculation and formula in [C46](AE-2026-001_C46_REGIONAL_CONTRIBUTIONS_TO_BASELINE_MISSINGNESS_MEAN_SHIFT_2026-10-28.md).


The 2026-only baseline-availability audits (C30/C31) identify a further selection caution: economies lacking the 2000 endpoint had lower pooled median 2019 productivity and higher median absolute 2019–2023 growth than the complete cases, while within-region rank comparisons differed materially. This does not establish a missingness mechanism or generalize to the 155-economy historical-vintage cohort. Excluding two extreme observations weakens, but does not eliminate, the absolute-growth rank contrast; the within-Sub-Saharan-African comparison reverses direction. With only 2019 and 2023 endpoints, the magnitude of net growth must not be called time-series volatility. Accordingly, pooled 153-versus-169 growth contrasts should not be interpreted as representative changes in the world's agricultural productivity.



The evidence supports three narrow conclusions. First, source release is a material component of descriptive country-level measurement uncertainty: an end-to-end median absolute annual growth revision of 0.4129 log-percentage points can coexist with relatively high rank correlation. Second, sign-change headlines are sensitive to small growth rates near zero and must be accompanied by magnitude thresholds. Third, changing the time horizon is not changing the data vintage: the weighted-average identity shows exactly why extending the endpoint from 2019 to 2023 can suppress shorter-period sign reversals.

A direct prior-art comparison is necessary: the documented `countryatlas::compare_vintages()` function reports **single-year level** revisions between archived WDI releases, whereas the present audit calculates **two-endpoint annualized growth-rate** revisions and their sign/rank sensitivity. The latter are standard downstream computations, not an original estimator. An exact head-to-head numerical benchmark would require identical release identities, endpoint years, country intersections and units; substituting a rolling `current` API result for the dated October 2026 extract would not guarantee identical source bytes. The original `countryatlas` source-code/estimand comparison is documented in the internal C7 audit, and the published function reference is cited below.

A further comparability issue is the **13th-versus-19th ICLS definition of employment and work**: the ILO documents differing country implementation dates and distinct database concepts. No country-specific standards transition is identified by our 2026-only worker check. Consequently, the observed worker-level discrepancies cannot be assigned to a changed ICLS definition, and the historical WDI vintage differences cannot be decomposed into ICLS, value-added and worker components without date-stamped component series and matching metadata (see [C29](AE-2026-001_C29_ILOSTAT_ICLS_STANDARD_AND_VINTAGE_IDENTIFICATION_GATE_2026-10-27.md)).

The C34 region-post-stratification exercise yields only a small hypothetical change in the 2000–2019 observed-country mean, but 60 missing endpoint pairs make the full 217-record mean unidentified. The counterfactual tipping-point algebra is assumption-dependent and must not be presented as evidence of missing-at-random or global representativeness. The new regional availability census (C33) shows complete-case coverage ranging from 1/3 to 6/6 across the seven WDI metadata regions, with strong differences in region denominators and territory composition. This reinforces the restriction to **descriptive selected-country results**, not a population-weighted global statement. The missingness mechanism remains unidentified.

The new C36 partial-identification exercise makes the distinction between **sign** and **magnitude** explicit: for the 217-record 2026-only finite frame, the median 2000–2019 growth sign is positive even under unrestricted missing rates, but its exact value remains in a broad sharp interval. This does not cure selection bias, identify historical revisions, or establish a world-representative trend. It is a standard order-statistic sensitivity calculation, not a new estimator.

The limitations are substantial. Revisions to the published composite indicator cannot be assigned to independent national-accounts or ILO employment mechanisms without matched historical component archives. Current-source ILOSTAT agreement does not provide independent provenance because the sources overlap. The fixed 155-country panel is selected by data availability, not a representative sample of world agriculture. The 2024 archive's missing 2023 endpoint prevents a three-vintage 2000–2023 comparison. The actual `countryatlas` CAGR function has been benchmarked, but the separate three-vintage `compare_vintages` prior-art benchmark remains incomplete. Prior research already studies statistical data revisions, and this study does **not** establish methodological novelty. The post hoc analysis is not preregistered, and the manuscript has not been externally reviewed.

The appropriate application is as a transparent, reproducible descriptive data note or methodological case study **if a suitable journal accepts this limited contribution and the human author approves the scientific and publication conditions**. It must not be presented as a new theory of agricultural productivity, a causal explanation of revision, or a new measurement of agricultural employment.

The C38 sharp prevalence bounds further restrict interpretation of the C36 positive-median result: a majority of the **217 equally weighted economy/territory records** has positive observed-or-unobserved growth under all assignments of the 60 missing rates, but **not every region** has a robust positive majority, and stronger growth thresholds need not command a majority. Neither finding identifies the missing values, validates historical WDI vintages or measures world worker-weighted agricultural productivity. The threshold exercise is post hoc and uses standard partial-identification arithmetic, not a novel estimator.

The C45 comparison further shows that retaining all 169 economies with both 2019 and 2023 values instead of requiring the 2000 baseline shifts the descriptive 2019–2023 signed-growth median by only **0.0846709** log-percentage points/year in this release. The small median shift is not a test of ignorable missingness or evidence of robustness in other vintages, and it does not resolve the countryatlas prior-art benchmark.

## 5. Conclusion

Across the same 155 economies, three official WDI releases yield meaningfully different annualized historical agricultural value-added-per-worker growth estimates. Country-level release provenance, fixed-sample selection, scale convention and time-horizon definition are necessary for defensible interpretation. Historical employment-source attribution and novelty remain unresolved. **The manuscript is not yet cleared for submission.**

## Data, code, ethics and author declarations

**Data and code availability:** source-file names, SHA256 checksums, source code and execution IDs appear above and in the main repository manuscript. CI artifacts may expire; the committed observed-country CSV and methods should be preserved with the eventual submission. **Ethics:** only publicly available country-level secondary statistics are analyzed; no claim is made about a human-subjects ethics-board determination. **Funding, competing interests, AI use, author contributions, identity and affiliation, journal choice, rights and publication fees:** **NOT VERIFIED — HUMAN AUTHOR DECISION REQUIRED**. No signature, journal submission, manuscript ID, acceptance or publication is asserted.

## References (verify final bibliographic formatting before submission)

1. World Bank. World Development Indicators, NV.AGR.EMPL.KD. https://data.worldbank.org/indicator/NV.AGR.EMPL.KD
2. International Labour Organization. ILOSTAT. https://ilostat.ilo.org/
3. Gutierrez L. (2002). Why is agricultural labour productivity higher in some countries than others? *Agricultural Economics Review* 3(1):58–72. DOI: 10.22004/ag.econ.26431.
4. Eberhardt M, Teal F. (2013). Structural change and cross-country growth empirics. *World Bank Economic Review* 27(2):229–271. DOI: 10.1093/wber/lhs020.
5. Dieppe A, Matsuoka H. (2021). Sectoral Decomposition of Convergence in Labor Productivity: A Re-examination from a New Dataset. World Bank Policy Research Working Paper 9767. A revised journal article appeared in *Empirical Economics* 68(4):1829–1859 (2025); these are distinct bibliographic versions.
6. Gollin D, Lagakos D, Waugh ME. (2013). The Agricultural Productivity Gap. NBER Working Paper 19628. DOI: 10.3386/w19628.
7. Johnson S, Larson W, Papageorgiou C, Subramanian A. (2013). Is newer better? Penn World Table revisions and their impact on growth estimates. *Journal of Monetary Economics* 60(2):255–274. DOI: 10.1016/j.jmoneco.2012.10.022.
8. Filer RK, Hájková D, Hanousek J. (2004). The Other Side of the Moon: The Data Problem in Analysing Growth Determinants. CEPR Discussion Paper 4349.
9. World Bank. WDI database archives. https://databank.worldbank.org/databases/archives
10. Yu Y. *countryatlas* 3.0.0: `compare_vintages` documentation (single-year WDI release-level comparisons). https://pursuitofdatascience.github.io/countryatlas/reference/compare_vintages.html . Package DOI: 10.32614/CRAN.package.countryatlas.

11. International Labour Organization. New ILO database updates work-related indicators to meet latest standards. ILOSTAT methodological explainer (2022). https://ilostat.ilo.org/blog/new-ilo-database-updates-work-related-indicators-to-meet-latest-standards/
12. International Labour Organization. Rilostat repository, data-licensing and access guidance (ILOSTAT datasets generally CC BY 4.0 since 3 May 2023 unless otherwise indicated). https://github.com/ilostat/Rilostat

**Critical internal AI decision:** MAJOR REVISION / NO SUBMISSION. The author-facing manuscript is a **real, consolidated output** but is not evidence of a completed peer-reviewed paper or author approval.

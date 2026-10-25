# Country Coverage and Agricultural Labor-Productivity Trends in World Development Indicators, 2000–2023: A Reproducible Descriptive Audit

**Manuscript status:** research draft, 25 October 2026. Proposed human author: Mojtaba Roozegar (subject to real scientific contribution, verification and explicit final approval). This text is **not** an accepted or submitted journal article. No fabricated data, causal effects, significance tests or novelty priority are asserted.

## Abstract

**Background:** Cross-country agricultural labor-productivity comparisons can be affected by uneven data availability, changing country coverage and the use of national-account and employment-model estimates. **Objective:** To document the observed country-year coverage of the World Bank's agricultural, forestry and fishing value added per worker indicator and compare descriptive annualized trends under available-pair and fixed-country samples. **Methods:** We independently retrieved official World Development Indicators (WDI) series NV.AGR.EMPL.KD for 2000, 2019 and 2023, excluded World Bank aggregate regions and income groups using country metadata, and retained only positive nonmissing endpoint observations. For each country, annualized log change was computed over 2000–2019 and 2000–2023. A common three-year complete-case panel was compared with each period's available pairs. The source snapshot and executable analysis were archived and a separate GitHub Actions job reproduced the principal results. **Results:** Of 217 nonaggregate economies, 158, 173 and 169 had positive observations in 2000, 2019 and 2023, respectively. Complete endpoint pairs numbered 157 (2000–2019) and 153 (2000–2023); 153 had all three years. The median annualized log changes were 0.02356 and 0.02224, respectively, in available pairs. In the common 153-economy sample the corresponding medians were unchanged, while the 2000–2019 mean shifted slightly from 0.02398 to 0.02402. **Conclusions:** Positive descriptive medians coexist with substantial nonrandomly selected country-year missingness. These results do not estimate worldwide worker-weighted gains, convergence, causation or welfare effects. A claim of incremental methodological novelty remains unverified.

**Keywords:** agricultural labor productivity; World Development Indicators; missing data; country panel; structural transformation; reproducibility.

## 1. Introduction

Agricultural labor productivity is a widely used aggregate indicator in development economics, but it is neither an unmediated observation of farm performance nor a comprehensive measure of rural welfare. In international statistics, sector value added must be defined and measured through national accounts, and agricultural employment is estimated from labor-market data that can vary in scope, timing and model-based adjustment. Cross-country differences in the indicator therefore combine economically meaningful variation with heterogeneous measurement systems. Even when all series are reported in constant US dollars, price-base comparability alone does not ensure that workers, hours, unpaid family labor and agricultural activities are observed consistently across countries.

The substantive economics of agricultural productivity is not new. Gutierrez (2002) examined productivity differences and conditional convergence across 44 countries. Eberhardt and Teal (2013) demonstrated that heterogeneous sectoral technologies complicate cross-country growth inference. Dieppe and Matsuoka (2021; subsequently published in 2025) analyzed sector-specific convergence and structural reallocation, including agricultural productivity. Gollin, Lagakos and Waugh (2013/2014) identified important discrepancies between aggregate sector value-added-per-worker measures and microeconomic measures of hours and human capital. This literature rules out presenting a simple new WDI trend chart as the first evidence of productivity growth or convergence.

A more limited and auditable problem is the relationship between **which countries have observations** and the summary statistic used to describe a global country panel. A period-specific complete-pair median may change merely because different economies enter each interval, even if the underlying individual-country trajectories are not compared consistently. Conversely, restricting to a balanced panel fixes the identity of countries but may exacerbate selection bias because data-poor economies are excluded. The present analysis does not purport to solve these problems. It records the data availability and tests the descriptive sensitivity of two intervals to a fixed-country restriction, using a dated, reproducible official-source extract.

The research questions are therefore deliberately narrow: (i) how many nonaggregate economies have valid agricultural value-added-per-worker observations in the selected WDI years; (ii) what are the median and mean annualized log changes among countries with valid endpoint pairs; and (iii) do these descriptive summaries change when the same countries are required to have all three years? No hypothesis of causal policy effects, farmer-level change or cross-country beta-convergence is tested.

## 2. Data and methods

### 2.1 Indicator and provenance

We used World Bank WDI indicator **NV.AGR.EMPL.KD**, described as *agriculture, forestry, and fishing, value added per worker (constant 2015 US$)*. The public WDI record identifies World Bank national accounts and ILOSTAT as sources. Values were retrieved from the official API for 2000, 2019 and 2023, along with the World Bank country metadata endpoint. The retrieved WDI indicator responses were labeled **last updated 8 October 2026**. The version-controlled observed-country panel is supplied as `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`; this document reports a dated snapshot, not an immutable official release.

We excluded entries with World Bank country-metadata `region.id = NA`, which represent aggregates, and retained 217 country/economy entries. This operational classification should not be confused with sovereign-state membership or with a fixed list of UN countries. Countries with missing indicator values remained in the denominator of the coverage table but were excluded from each paired-growth calculation. No missing value was set to zero or imputed. We accepted positive finite observations only because log changes are undefined for nonpositive endpoints.

### 2.2 Descriptive estimands

For economy `i` and endpoint `t` (2019 or 2023), let `y_it` denote reported constant-2015-dollar value added per agricultural worker. The annualized log change is

`g_i(2000,t) = [ln(y_it) - ln(y_i,2000)] / (t - 2000)`.

We report the arithmetic mean and median of `g_i` across eligible economies. The statistics are **equally weighted by economy**, not by agricultural workforce, production, population, irrigated area or economic output. They must not be described as the growth of global agriculture. The 2000–2019 endpoint comparison requires both 2000 and 2019 to be observed, while 2000–2023 requires 2000 and 2023. The balanced-sample sensitivity analysis requires all three years to be present and positive for the same economy.

The design is purely observational and descriptive. No standard errors, statistical significance tests, confidence intervals, causal counterfactuals or time-series break adjustments were prespecified or estimated. Regional summaries, where mentioned, are exploratory and use the official region field from the dated country metadata response.

### 2.3 Execution and checks

The API extract and country-level analysis were independently reproduced in the read-only GitHub Actions job [run 40210367783](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40210367783), which completed successfully on 25 October 2026 and uploaded [observed-data artifact 12605590746](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40210367783/artifacts/12605590746). Its log reported 217 nonaggregate economies, 157 and 153 complete endpoint pairs, and the same two unrounded medians as the independently obtained official-source panel. The artifact is retained temporarily by the CI service; the version-controlled CSV preserves the key source observations after artifact expiry. The analysis script uses only the Python standard library and stores API source URLs and missingness summaries.

## 3. Results

### 3.1 Data coverage

The official API returned 266 indicator records per selected year before excluding aggregate groups. Country metadata contained 296 entries; after aggregate exclusion, the analysis set contained **217 economies**. A positive value was available for **158 (72.81%)** in 2000, **173 (79.72%)** in 2019 and **169 (77.88%)** in 2023. Only **153 (70.51%)** had positive observations in all three years. Thus 64 of the 217 economy records could not contribute to a common three-year comparison. This coverage pattern is a descriptive property of the selected indicator and release; it is not evidence that excluded economies had zero production or zero productivity.

### 3.2 Period-specific versus balanced-sample summaries

For 2000–2019, **157** economies had valid endpoint pairs. Their median annualized log change was **0.023555752946417118** (approximately 2.36 log-percentage points per year), and the mean was **0.023984983654433946** (approximately 2.40). Restricting the same interval to the **153** economies with all three observations left the median unchanged at **0.023555752946417118**, while the mean became **0.024020706240511433** (approximately 2.40). This difference in mean is small in this snapshot but cannot be assumed to be small in other releases, indicators or country groupings.

For 2000–2023, **153** economies had valid endpoint pairs, identical in count to the three-year balanced panel. The median annualized log change was **0.02224483704398673** (approximately 2.22 log-percentage points per year), and the mean was **0.020785340670841517** (approximately 2.08). Both values are descriptive rates computed from two endpoint observations, not annual growth observations averaged over the intervening years.

### 3.3 Regional coverage as an inferential warning

The 153-economy balanced sample contains **45** entries classified as Europe & Central Asia, **36** as Sub-Saharan Africa, **28** as Latin America & Caribbean, **22** as East Asia & Pacific, **15** as Middle East, North Africa, Afghanistan & Pakistan, **6** as South Asia and **1** as North America. These are metadata categories from the current WDI response, not stable country groupings across all historical years. In particular, a regional summary based on one North American country cannot represent the region. Regional median differences were not tested and must not be interpreted as structural or policy effects.

## 4. Discussion

The principal result is methodological modesty rather than a newly discovered economic law. A widely used official indicator is missing for a material fraction of the nominal country set in all three selected years. A common-country restriction produces a reproducible descriptive comparison, but does not eliminate missing-not-at-random selection. The observed median difference between 2000–2019 and 2000–2023 also combines different end years and time intervals, including economic and environmental events after 2019, so it cannot be assigned exclusively to coverage changes. Indeed, the 2000–2023 sample coincides with the three-year balanced set here; this specific sample provides little evidence of large median sensitivity to the balanced restriction.

Country-level value added per worker may rise when measured agricultural employment falls, even if output, working hours, land productivity or household income follow different trajectories. Comparisons may also be affected by ILO modeled employment, the treatment of informal or family labor, re-benchmarking of national accounts, sector reclassification, currency conversion and different availability of historical estimates. These mechanisms cannot be quantified from the present single indicator. A stronger study would jointly retrieve sector value added and agricultural employment components, record revisions over successive data releases, and compare country- versus worker-weighted trends while carefully acknowledging changes in definitions.

Prior research provides both substantive and methodological reasons for restraint. Gutierrez (2002) and Dieppe and Matsuoka (2021/2025) already discuss agricultural labor-productivity patterns and convergence; Eberhardt and Teal (2013) show why cross-country sector heterogeneity matters; and Gollin and colleagues highlight the sensitivity of aggregate productivity gaps to labor-input measurement. The current work must therefore not be marketed as a first global analysis or a novel convergence result. Its potential incremental contribution is a transparent, **release-dated data-coverage and common-country reproducibility audit**, contingent on a deeper literature comparison that establishes whether that narrow question is worth publishing.

## 5. Limitations

This analysis examines only three endpoint years of one public series. It does not reconstruct historical WDI revisions, assess uncertainty in ILO employment estimates, inspect original national data, model dependence across economies, identify causal determinants or distinguish output-per-hour from output-per-worker. The balanced panel is selected on data availability, potentially inducing selection bias. Equal-country-weighted statistics are not global worker-weighted statistics. No inferential uncertainty is reported; regional subsamples can be small or unrepresentative. The report is an initial empirical manuscript draft and its publication-level novelty has not been established.

## 6. Conclusions

The official WDI snapshot contains 217 nonaggregate economies, but only 153 have positive agricultural value-added-per-worker observations for all three selected years. Descriptive median annualized log changes are positive for both 2000–2019 and 2000–2023; their interpretation is limited to the countries with observed endpoints. A fixed-country comparison is feasible and reproducible, but neither fixes measurement heterogeneity nor establishes convergence, causality or changes in farmer welfare. Any publication claim requires further sensitivity analyses, independent literature appraisal and substantive review by the accountable human author.

## References

1. World Bank. World Development Indicators. Indicator NV.AGR.EMPL.KD: Agriculture, forestry, and fishing, value added per worker (constant 2015 US$). https://data.worldbank.org/indicator/NV.AGR.EMPL.KD (official series; data accessed 25 October 2026).
2. International Labour Organization. ILOSTAT database, employment estimates underlying the WDI indicator. https://ilostat.ilo.org/
3. Gutierrez L. (2002). Why is agricultural labour productivity higher in some countries than others? *Agricultural Economics Review*, 3(1), 58–72. https://doi.org/10.22004/ag.econ.26431
4. Eberhardt M, Teal F. (2013). Structural change and cross-country growth empirics. *The World Bank Economic Review*, 27(2), 229–271. https://ideas.repec.org/p/wbk/wbrwps/6335.html
5. Dieppe A, Matsuoka H. (2021). Sectoral Decomposition of Convergence in Labor Productivity: A Re-examination from a New Dataset. *World Bank Policy Research Working Paper* 9767; later published in *Empirical Economics* (2025). https://hdl.handle.net/10986/36232
6. Gollin D, Lagakos D, Waugh ME. (2013). The Agricultural Productivity Gap. *NBER Working Paper* 19628; subsequent journal publication. https://doi.org/10.3386/w19628

## Author and publication declarations — NOT FINAL

Human author contribution, affiliation, funding, competing interests, rights, AI assistance disclosure, journal and fees **remain unverified and require manuscript-specific author approval**. No ethics approval is asserted; this work analyzes public aggregate secondary statistics. No journal submission or publisher peer review has occurred.

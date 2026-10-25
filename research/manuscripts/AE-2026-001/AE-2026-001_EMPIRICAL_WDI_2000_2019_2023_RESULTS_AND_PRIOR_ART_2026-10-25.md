# AE-2026-001 — empirical source-observation and sensitivity results (NOT a submitted article)

**Research snapshot obtained 25 October 2026** from the official [World Bank WDI API](https://api.worldbank.org/v2/country/all/indicator/NV.AGR.EMPL.KD?format=json&date=2023&per_page=20000), which reports its underlying data as last updated **2026-10-08**. This is a genuine official-data result, not a synthetic test, but it has **not yet passed external peer review or novelty validation**.

## Original data and reproducibility

The version-controlled source extract is [AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv](AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv). Exactly 266 country/aggregate indicator rows were returned for each requested year; a separate World Bank metadata request returned 296 economy/group records. Following the World Bank metadata `region.id != "NA"` exclusion rule for aggregate groups, **217** named nonaggregate economies remain. These economy IDs are retained even if the indicator is missing; no zeroes were substituted for missing data. The official indicator is agricultural, forestry and fishing **value added per worker in constant 2015 US dollars**, built from World Bank national accounts and ILOSTAT employment estimates; it is not a farm-level productivity or welfare measure.

Official API source queries (recorded, not hypothetical):
- [WDI 2000 observations](https://api.worldbank.org/v2/country/all/indicator/NV.AGR.EMPL.KD?format=json&date=2000&per_page=20000)
- [WDI 2019 observations](https://api.worldbank.org/v2/country/all/indicator/NV.AGR.EMPL.KD?format=json&date=2019&per_page=20000)
- [WDI 2023 observations](https://api.worldbank.org/v2/country/all/indicator/NV.AGR.EMPL.KD?format=json&date=2023&per_page=20000)
- [World Bank country/aggregate metadata](https://api.worldbank.org/v2/country?format=json&per_page=20000)

### Descriptive measurement and missingness

| Indicator | Observed economies | Share of 217 |
|---|---:|---:|
| 2000 nonmissing positive | 158 | 72.81% |
| 2019 nonmissing positive | 173 | 79.72% |
| 2023 nonmissing positive | 169 | 77.88% |
| All three years observed | 153 | 70.51% |
| Paired 2000 and 2019 | 157 | 72.35% |
| Paired 2000 and 2023 | 153 | 70.51% |

Define for each economy `g_i(2000,t) = [ln(y_i,t)-ln(y_i,2000)]/(t-2000)`, requiring positive, observed values in both years. This is a descriptive annualized log change, **not** a causal treatment effect or a global agricultural-worker-weighted rate.

| Descriptive comparison | Countries | Median annual log change | Mean annual log change |
|---|---:|---:|---:|
| 2000–2019, available pair | 157 | 2.36% | 2.40% |
| 2000–2023, available pair | 153 | 2.22% | 2.08% |
| 2000–2019, **identical three-year balanced sample** | 153 | 2.36% | 2.40% |
| 2000–2023, **identical three-year balanced sample** | 153 | 2.22% | 2.08% |

A balanced sample does not eliminate nonrandom country exclusion; it makes the **set of included countries** identical. The time intervals differ (19 versus 23 years), so differences between annualized rates also reflect real events and measurement revisions, not merely attrition.

### Exploratory regional descriptive medians, balanced sample only

| World Bank region | Complete economies | Median 2000–2019 annual log change | Median 2000–2023 annual log change |
|---|---:|---:|---:|
| Europe & Central Asia | 45 | 3.69% | 3.27% |
| Sub-Saharan Africa | 36 | 1.78% | 1.46% |
| Latin America & Caribbean | 28 | 1.66% | 1.37% |
| East Asia & Pacific | 22 | 1.70% | 1.40% |
| Middle East, North Africa, Afghanistan & Pakistan | 15 | 2.10% | 2.33% |
| South Asia | 6 | 3.90% | 3.22% |
| North America | 1 | 2.77% | 2.93% |

**Important:** The North America category contains only **one** complete economy under the World Bank country/region metadata and selected indicator; a one-country value must never be presented as a regional estimate. Small samples and selection bias apply to other regional strata. These are not inferential confidence intervals, and there is no test of region differences or convergence here.

## Originality and adversarial interpretation

The *existence* of global agricultural productivity differences or convergence is well studied. [Gutierrez 2002](https://doi.org/10.22004/ag.econ.26431) analyzed agricultural labor productivity determinants and conditional convergence. [Eberhardt and Teal 2013](https://ideas.repec.org/p/wbk/wbrwps/6335.html) analyzed structural heterogeneity across countries and sectors. [Dieppe and Matsuoka 2021/2025](https://hdl.handle.net/10986/36232) decomposed sectoral labor-productivity convergence, finding an important role for agricultural productivity. [Gollin, Lagakos and Waugh 2013/2014](https://doi.org/10.3386/w19628) documented serious agricultural labor-input and productivity-measurement problems. Therefore **no new theory, first global panel, first convergence analysis or policy effect is claimed**. The narrow possible contribution is a *transparent, revision-dated missingness and balanced-country sensitivity audit* of this particular public WDI series, pending a literature audit for identical earlier comparisons.

**Scientific interpretation:** The median observed country annualized log change is positive in the available 2000–2019 and 2000–2023 pairs, but the calculation does **not** show that the same farmer, agricultural worker, or representative global workforce gained this amount, nor that irrigation technology or any policy caused it. Differences in series coverage, national accounts, modeled employment, country boundary definitions and outliers may be material.

## Mandatory next-stage gates

1. Re-run the stored CSV using independent offline code and compare exact counts, sample membership, and unrounded summary values to this source-observation report; check country identity and metadata version.
2. Audit World Bank country classification and unusual coverage (including North America n=1), model revisions, missingness mechanisms and comparability of constant-2015-USD series.
3. Conduct literature novelty review for a missingness-sensitivity method; if no defensible increment exists, **reject or substantially redesign** the paper rather than manufacture a novel conclusion.
4. Define robustness analyses (trimmed means, balanced-country set, uncertainty, GDP and employment component decomposition) *before* making inferential claims.
5. Produce an author-reviewed full article with genuine human scientific input and verified affiliation/funding/COI/AI disclosures before any journal submission.

**Stage decision:** AE-2026-001 has advanced from *source-identified pilot* to **observed-data descriptive analysis and results draft**. It is NOT a completed scientific article, validated novel study, peer-reviewed work, or submitted manuscript.

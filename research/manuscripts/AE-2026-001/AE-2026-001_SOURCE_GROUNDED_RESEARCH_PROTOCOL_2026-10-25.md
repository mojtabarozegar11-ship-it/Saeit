# AE-2026-001: public-source, reproducible research protocol

**Status:** new empirical research project, initiated 25 October 2026; NOT a finished, author-approved, submitted or peer-reviewed article. This is the third pipeline item, distinct from irrigation advice review MR-2026-001 and wheat RNA-seq reanalysis ZM-R01. Proposed sole human author Mojtaba Roozegar, contingent on substantial real contribution and final approval; ChatGPT is an AI research assistant, not human author or independent peer reviewer.

## Research question
**How do national agricultural labor-productivity trajectories between 2000, 2019 and 2023 change when missing country-year coverage is made explicit?** The proposed paper is a descriptive and methodology-aware reanalysis, not a claim of causal effect or new economic mechanism.

**Working English title:** Agricultural Labor Productivity Dynamics and Data-Coverage Sensitivity in a Global Country Panel, 2000–2023.

## Verified public data and definitions
- Official [WDI indicator NV.AGR.EMPL.KD](https://data.worldbank.org/indicator/NV.AGR.EMPL.KD), agriculture, forestry and fishing value added per worker in constant 2015 USD, reported using World Bank national accounts and ILOSTAT labor statistics. WDI site displays CC BY 4.0. This is NOT farm-level income, crop yield, causal technology adoption or individually measured productivity.
- [World Bank WDI indicator metadata](https://databank.worldbank.org/metadataglossary/world-development-indicators/series/NV.AGR.EMPL.KD): agricultural sector definition and constant-2015-dollar reporting.
- Public [World Bank indicator API](https://api.worldbank.org/v2/country/all/indicator/NV.AGR.EMPL.KD?format=json&per_page=20000&date=2000%3A2023) and [country metadata](https://api.worldbank.org/v2/country?format=json&per_page=20000) for country inclusion and aggregate exclusion.

## Versioned analytic design and actual execution gate
The committed source file [wdi_agricultural_productivity_pilot.py](analysis/wdi_agricultural_productivity_pilot.py) uses Python standard library only. It fetches current WDI data and country metadata from the official APIs with retries, refuses unexpected pagination, distinguishes countries from regional/income aggregates using source metadata, retains explicit missingness, computes *descriptive* annualized mean/median log change for observed country pairs in 2000–2019 and 2000–2023, and preserves exact input API URLs. No treatment effect, statistical significance or causality is inferred.

The read-only GitHub Actions workflow is [.github/workflows/ae-2026-001-wdi-agricultural-productivity-pilot.yml](../../.github/workflows/ae-2026-001-wdi-agricultural-productivity-pilot.yml). It first runs a synthetic self-test; if the live WDI download succeeds, the workflow retains an observed-country CSV and source/missingness JSON for seven days. The workflow file being registered is **not** proof that its GitHub Actions execution completed. No live-data results are asserted here.

## Mandatory gates before a scientific manuscript is complete
1. Confirm successful actual GitHub Actions run and source-downloaded data artifact, with run URL, timestamp, country rows and missing-data fractions; no results from synthetic unit tests.
2. Audit whether WDI and ILO modeled employment, national accounts series breaks, rebenchmarks, changing country boundaries, and source revisions compromise comparability.
3. Complete original primary-literature novelty search on agricultural labor productivity convergence and structural transformation; reject or substantially narrow a redundant question rather than fabricate novelty.
4. Distinguish country-weighted medians, agricultural-worker-weighted global trends and inclusion/exclusion bias. Do not equate arithmetic share changes with welfare gains or farmer earnings.
5. Predeclare any sample filters and robustness checks before inferential modeling, disclose nonrandom missingness, avoid unjustified causal extrapolation.
6. Obtain genuine human scientific analysis and author revision, verified identity/affiliation, funding/COI/AI disclosure, publication rights, journal/fee and manuscript approvals before submission.

**Current gate:** source and runnable protocol created; successful live-data execution **not yet verified**; full manuscript, separate QC, author approval, submission, Manuscript ID and publication all **pending**. This newly initiated project demonstrates continuity of the production queue but does not count as a completed article.

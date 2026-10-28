# FS-2026-001 — independent fourth-paper research candidate (NOT an article draft)

**Created 2026-10-25. Status: SOURCE-CONFIRMED / SCIENTIFIC NOVELTY NOT CLEARED / NO DATA ANALYSIS PERFORMED / NO HUMAN AUTHOR APPROVAL.** This is a unique queued candidate, not a completed or even started manuscript; do not count it as a full article or journal submission.

## Distinct scientific question

**Proposed falsifiable question:** In a harmonized country–year panel, is the association between national **cereal yields** and **unaffordability of a healthy diet** stable after adjusting for income, inflation, cereal import reliance and country/year fixed effects, or is the apparent relationship largely explained by the mismatch between staple production and access to diverse nutritious foods?

This is conceptually separate from MR-2026-001 (evidence provenance of irrigation advice), ZM-R01 (wheat factorial RNA-seq) and AE-2026-001 (sectoral labor-productivity measurement). It is not an extension of AE's three-year descriptive WDI sample. An association, if observed, is not automatically causal; no natural experiment is yet identified.

## Verified legitimate source paths (source existence, NOT dataset retrieval)

1. **FAO FAOSTAT** official portal, https://www.fao.org/faostat/en/, updated 2026-10-09 and earlier 2026 releases, lists crop and livestock products, and the **Cost and Affordability of a Healthy Diet** domain. The CoAHD series and data-revision metadata must be downloaded in a frozen vintage with original area codes, units and flags. A public portal is not evidence that any specific numerical observation has been collected in this project.
2. **FAO official CoAHD catalog**, https://data.fao.org/catalog/dataset/b8f254c0-40a0-4911-90e5-0208c60917dd, describes a national annual panel beginning in 2017, with PPP dollar and local-currency cost and population unable-to-afford indicators. **Warning:** publisher catalog metadata for 2025 gives 2017–2024 coverage; the 2026 portal may have updated the vintage. Do not mix editions or assert identical observations without download-date and schema checks. Source pricing uses ICP, WDI, FAOSTAT and World Bank Poverty and Inequality Platform, including estimated/imputed series.
3. **World Bank Food Prices for Nutrition**, https://datacatalog.worldbank.org/search/dataset/0061222/food-prices-for-nutrition-fpn, explains how the July 2025 FPN 4.0 benchmark and price/income revisions can change apparent cross-year trends. Versioned methodology and imputation must be recorded. Do not treat derived affordability as an independently surveyed national observation for every country-year.

## Required preregistered data and originality gates BEFORE starting an article

- Download and SHA256-freeze **real** FAOSTAT crop yield and CoAHD files and World Bank country income/price data using official authorized APIs/bulk CSV, no paywall bypass, no commercial cloud charges. Record publication vintage, country codes, source licences, missingness and estimate flags.
- Test **measurement comparability**: yield in kg/ha vs total food availability; PPP dollar cost vs affordability share; nominal/real price inflation; 2021 ICP price benchmark and source-imputed years; FAOSTAT and WB country-code joins; exclude regional aggregates and countries with no actual observations.
- Register outcome **healthy-diet unaffordability percentage** (not cost as a synonym), predictors cereal yield and trade exposure, confounders income and inflation, fixed effects, sensitivity to imputed affordability data and alternative lags. Report uncertainty and observational limitations; do not claim a yield-policy effect without a credible identification strategy.
- Search and critically compare FAO SOFI 2026, Food Prices for Nutrition research, and peer-reviewed literature on production–nutrition access decoupling. If the research question and estimator duplicate established analyses, **reject/redesign** this candidate before counting an original Research article. Do not slice the same panel into repetitive manuscripts.
- Have the intended human author approve the question, inspect sources, make substantive scientific decisions and confirm all journal/ethics/AI/funding/COI/rights disclosures before any submission.

**Next state only after actual source files and a defensible prior-art gap:** `FS-2026-001` may move from `queued_candidate` to `source-verified protocol`; from there only real results, independent QA and human author revision can make a manuscript. No figures, findings, p-values or author contribution are claimed.

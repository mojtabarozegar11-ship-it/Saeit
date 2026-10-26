# AE-2026-001 C8 — official ILOSTAT absolute agricultural employment: source-eligibility and vintage-match gate

**Date:** 26 October 2026. **Assessment:** Internal AI source and methods review, not human peer review. **Decision:** a primary-source *absolute employment* dataset family is identified, but independent denominator validation is **NOT COMPLETE**; article remains MAJOR REVISION / NO SUBMISSION.

## New primary-source finding

The ILOSTAT official data catalogue, https://ilostat.ilo.org/data/ (read 26 October 2026), explicitly lists **“Employment by sex and economic activity (thousands)” — Annual**, as well as the annual **“Employment by sex and economic activity - ISIC level 2 (thousands)”** series. These are absolute numbers in *thousands of persons*, unlike the World Bank/ILO indicator `SL.AGR.EMPL.ZS`, which is the **percentage of total employment in agriculture**. The source family therefore passes the **unit-type eligibility** test for an independent agriculture employment denominator, but **no matching ILOSTAT CSV, release-vintage archive, or country-year values were downloaded or reconciled in this review**. The catalogue's existence is not evidence that all 155 economies or both 2000/2019 endpoints are available, or that its values match the WDI denominator.

## Required exact comparability protocol before any empirical validation claim

1. Download the official annual ILOSTAT **employment by sex and economic activity (thousands)** file, recording the *actual* downloadable URL, retrieval timestamp, bytes, SHA256, indicator code, catalogue metadata and release/version date. Do not invent an indicator code from search snippets.
2. Retain total sex, agricultural economic activity (ISIC section A where supported), total employed persons, annual frequency, and a single consistent classification; record which classification revision is used and whether it covers agriculture, forestry and fishing.
3. Confirm country-code crosswalk, national territory, observation year 2000 and 2019, employment concept, sex/age coverage, survey versus modeled source status, time-series breaks and missingness. Do not substitute employment *share* or labor force counts for agricultural workers.
4. Match **2024 and 2025 historical releases** to the corresponding WDI archives *if available*. A current ILOSTAT download, even with 2000/2019 historical years, is **not** a historical 2024/2025 vintage. If matching releases cannot be recovered, explicitly label any comparison **cross-source level plausibility at the current release**, not historical revision attribution.
5. Compute the WDI algebraically implied `L* = NV.AGR.TOTL.KD / NV.AGR.EMPL.KD` in **persons**, compare against ILOSTAT thousands after multiplying by 1000, report coverage and residual distribution by economy/year/vintage, and avoid interpreting the identity as independent evidence. Source metadata may differ even when units match.
6. Apply the same 155-economy intersection only to complete, truly comparable observations; disclose attrition and avoid filling missing values or treating a cross-sectional source agreement as proof of causation.

## Scientific disposition

The previously reported 155-economy decomposition and 40/155 comparison remain an **algebraic identity**, not an ILOSTAT-validated employment mechanism. The independent source family is now concretely identified and the validation pathway is specified; the missing release-aligned dataset is still a publication blocker for claims about independently observed employment revisions. No new quantitative employment result, manuscript novelty, causal conclusion, or submission is asserted.

**Sources:** [ILOSTAT official data catalogue](https://ilostat.ilo.org/data/); [World Bank indicator SL.AGR.EMPL.ZS](https://data.worldbank.org/indicator/SL.AGR.EMPL.ZS).
# FUT-012 Wheat — first-pass source, prior-art and license screen

**28 October 2026 | FUTURE QUESTION ONLY | NOT AN ACTIVE MANUSCRIPT OR VERIFIED NOVELTY**

## Candidate question
How are country-level wheat yield anomalies associated with heat and precipitation anomalies after accounting for country/year effects, changing harvested area, and the ecological mismatch between weather grids and actual wheat-growing locations?

## Direct prior art and novelty gate
- Schmidt & Felsche (published online 21 Dec 2023; 2024 issue), DOI 10.1002/cli2.61, already analyze wheat/maize/barley yield anomalies in EU producing countries with climate variables and nonlinear models over 1961–2020. Publisher abstract: https://rmets.onlinelibrary.wiley.com/doi/abs/10.1002/cli2.61 .
- Riedesel et al. (2023), DOI 10.1371/journal.pone.0288202, specifically study timing and intensity of heat/drought stress and wheat yield losses in Germany: https://openalex.org/W4385260463 .
- Bocchi et al. (2026), preprint https://arxiv.org/abs/2601.12864, examine within-season temperature and precipitation anomalies for soft wheat in Italy. **Preprint, not treated as peer-reviewed confirmation.**

**Preliminary originality decision:** The broad heat/precipitation-versus-wheat-yield question is **already occupied**; simply fitting a country panel is not a demonstrated novelty. A defensible narrower question would require a preregistered external validation, cross-resolution exposure-error correction, or documented new policy-relevant identification strategy with data support. No such contribution has been established.

## Data feasibility and rights
- FAO's current catalog entry for national crop production/yield/harvested area reports annual coverage 1961–2024, yield in hg/ha and a **CC BY 4.0** license, with a 15 Dec 2025 revision: https://data.fao.org/catalog/iso/d24a448b-3b62-4c09-8c1d-4a39bb599876 .
- A *different, older* FAO catalog entry for a similarly named crop dataset advertises **CC BY-NC-SA 4.0**: https://data.fao.org/catalog/dataset/crop-production-yield-harvested-area-and-processed-global-national-annual-faostat . The exact release/file license and permitted reuse must therefore be checked **per actual download**; no blanket commercial reuse authorization is inferred.
- NASA POWER's official daily API describes analysis-ready daily meteorological data: https://power.larc.nasa.gov/docs/services/api/temporal/daily/ . The project requests citation and publicly documents access, but a concrete coordinate/time window, missing-value audit and resolution suitability are still untested. Do not mass-scrape global grid cells.
- Country-level wheat yield cannot be defensibly linked to one national-centroid weather point; crop-area weighting and phenology/crop-calendar compatibility are required. Country/year panel data availability and licensing are **plausible at portal level only**, not verified at joined-record level.

## Next-stage gates
1. Obtain version-locked wheat-yield data and data-specific license/attribution metadata.
2. Select wheat-area weights, growing-season calendars, climate grid and temporal coverage, documenting any bias from a single national centroid.
3. Run a focused systematic prior-art screen for cross-resolution weather exposure and wheat-yield anomaly models.
4. Specify estimand, missing-data rules, placebo/negative controls and out-of-time validation **before** computing results.
5. Require independent critical review and author approval before activating this question as a manuscript.

**Decision:** `FUT-012 = SCREENED_PRELIMINARY / HOLD`; no new paper, no data download, no model fit, no claimed novelty. MR, AE and ZM remain the production priority.

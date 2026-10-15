# Astra V2 — US water/land margin product: real-source pilot research

**Checked on:** 2026-10-15 (UTC)  
**Scope:** one private opportunity review, `farm_water_land_margin_audit_v1`.  
**Disposition:** **NO-GO for a paid release in its current form; continue bounded private research.**  
**Public sale / automated release / payment:** NOT AUTHORIZED.

## Why this investigation exists

This pilot uses actual external primary/institutional pages and the existing independent Astra V2 product source. The sources establish a **real agricultural planning problem and strong existing competition**; they do *not* establish buyer intention, product differentiation, a commercial-quality grade, or a defensible sales price.

## External observations — provenance and limits

| Ref | Primary page / accountable publisher | Supportable observation | Evidence class | What it does NOT prove |
|---|---|---|---|---|
| E01 | [USDA ERS, Farm Sector Income Forecast; updated Sep 3 2026](https://www.ers.usda.gov/topics/farm-economy/farm-sector-income-finances/farm-sector-income-forecast) | U.S. 2026 agricultural production expenses are forecast at $492.8 billion, up $21.2 billion / 4.5% on the 2025 estimate. | Farm cost context, FORECAST | The forecast does not demonstrate demand for this software, or any user's willingness to pay. |
| E02 | [USDA NASS, 2023 Irrigation and Water Management Survey; released Oct 31 2024](https://data.nass.usda.gov/Newsroom/2024/10-31-2024.php) | The 2023 survey reported 212,714 farms and 53.1 million irrigated acres, with 81 million acre-feet of irrigation water applied in the United States. | Scale / resource-use context, HISTORICAL SURVEY | Not a 2026 farm count and not a customer or pricing study. |
| E03 | [UC Davis Agricultural Water Center — Tools](https://agwater.ucdavis.edu/tools) | The Water-Land-Crop Allocation Optimization Planning Tool models multi-year mixes and water/rotation constraints. | Directly comparable incumbent solution | Cannot claim that our simpler two-resource calculator is a unique category or better. |
| E04 | [Kansas State University — Crop Water Allocator](https://milab.ksu.edu/crop-water-allocator) | University software already addresses crop mix, land and constrained irrigation-water allocation with net-return optimization. | Direct competitor / established methods | No proven unmet need just because a similar program exists. |
| E05 | [FAO — CROPWAT](https://www.fao.org/land-water/resources/tools/software/cropwat/en) | Established decision support covers crop-water needs and irrigation scheduling based on crop, soil and climate data. | Technical benchmark / alternative | Our calculator does not model crop evapotranspiration or certify physical irrigation plans. |
| E06 | [UC ANR — CropManage](https://cropmanage.ucanr.edu/) | Free web-based irrigation and nutrient recommendations, using weather, soil and crop information. | Free competing workflow | Water-margin calculations alone are not a sufficient differentiator. |
| E07 | [University of Maryland Extension — Crop Budgets](https://www.extension.umd.edu/programs/agriculture-food-systems/program-areas/farm-and-agribusiness-management/grain-marketing/crop-budgets) | Free web-based crop budgeting and grain marketing analysis already allow editable farm-cost assumptions. | Free farm-finance competitor | Generic spreadsheet/economic reports cannot automatically command a paid premium. |
| E08 | [University of Nebraska — ACREE 2026](https://cropwatch.unl.edu/register-now-acree-nebraskas-free-irrigation-scheduling-app-ready-2026-season/) | A free 2026 irrigation scheduling application estimates soil-water depletion from field and weather inputs. | Free irrigation competitor | Does not by itself disprove an integrated financial planning opportunity. |
| E09 | [University of Wisconsin-Madison Extension — Crop Enterprise Budget Tool](https://farms.extension.wisc.edu/articles/using-the-crop-enterprise-budget-tool/) | An existing enterprise-budget spreadsheet models per-acre production cost and returns. | Free/basic finance alternative | Does not prove any paid demand for our product. |

These are **nine public-page references**, not nine independent buyer testimonials or verified market-demand attestations. Several share university/USDA institutional ownership. All figures must retain their original source year. Links, bibliographic facts and brief independent paraphrases only: do not reproduce source tools, datasets, code, figures or protected content without license review.

## Internal review action: one actual source-built prototype

- Existing source: [Farm Water & Land Margin Audit README](../product_prototypes/farm_water_land_margin_audit/README.md)
- Engine: [water_margin_audit.py](../product_prototypes/farm_water_land_margin_audit/water_margin_audit.py)
- Mathematical model: a continuous 2-resource, 2–5 crop linear allocation model using user-provided land, water and crop-specific gross margin, plus a user-defined drought sensitivity case; exact Decimal-based candidate evaluation.
- All bundled example values are **synthetic**; source/status labels can refer to operator estimates/records, but those are not independently audited by this prototype.
- The current model omits nonlinear irrigation/yield response, regulations, soil suitability, rotations, seasonality, labor and operational constraints. It is **not** a field-ready irrigation or farm management recommendation.
- Historical synthetic mathematical regression passes do not establish external technical or commercial certification.

## Product-positioning assessment

**Broad generic irrigation optimizer for sale: NO-GO.** UC Davis and K-State already address similar or richer allocation questions, and FAO / UC ANR offer related tools. That is a substantive competitor obstacle, not an argument to generate more ZIP files.

**Conditional research hypothesis (not verified):** a transparent, privacy-preserving, offline consultant worksheet that joins *farm-specific* gross-margin sensitivities and constrained water allocation in an explainable audit trail may help small operators who want reproducible client reports. Compare against the exact workflows above. Do not assert superiority, portability, accessibility or willingness-to-pay before controlled usability tests.

## Required discriminating next actions

1. Record a feature-by-feature gap matrix against UC Davis and K-State: constraints, field usability, export formats, explainability, local/offline availability, source transparency and maintenance. **No assumed missing competitor capabilities.**
2. Recruit consenting target users for problem interviews and witnessed competitor comparisons; record exact anonymized responses, not simulated testimonials. Test economic value and willingness to pay separately.
3. Obtain real farm inputs with permission, documented source units and provenance; verify outputs with an agronomist and agricultural economist. Never substitute fictional examples for data.
4. Implement only demonstrably needed differences and test security, accessibility, mathematical reproducibility, agronomic warnings, onboarding, export, help/support and licensing.
5. Build a product-specific dossier toward the **100 independently checked evidence item target**, with deduplicated documents and reviewed claims. The nine external links above are a research start, **not** a completed 100-item dossier.
6. Leave retail price, 90% discount, commercial score, release approval, actual sales and revenue as **UNASSESSED / NOT AUTHORIZED** until an independent commercial review and real paid-fulfilment tests succeed.

## Non-interference

This is a **human-readable, non-commercial research artifact committed to the repository**. It does not change the historical 0048 SQLite, the dormant 0049 candidate, the five-minute private tick, any product archive, the MojPlayWin store, checkout or payment processor. No live buyers were contacted. No factory publication or 0049 deployment is claimed.

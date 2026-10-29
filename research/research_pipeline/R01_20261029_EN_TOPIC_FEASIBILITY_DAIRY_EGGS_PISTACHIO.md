# R-01 future English research bank — first three feasibility dossiers (29 October 2026)

**State:** RESEARCH_QUESTION_CANDIDATES_ONLY. None is a finished article, tested hypothesis, registered study, novel discovery, author-approved protocol or publication. Current MR/AE/ZM scientific blockers retain priority. No human/animal recruitment or data purchase is authorized.

## AGR-FUT-001 — Dairy cattle: national milk productivity and heat exposure
**Precise question:** In countries with continuous annual reporting during a pre-fixed overlapping period, does within-country change in annual mean temperature / heat-related proxy correlate with changes in *reported* cow-milk output per reported dairy animal, after accounting for country and year fixed effects? **Do not** claim an animal-level temperature-humidity index from annual temperature alone.

**Gap to verify before writing:** Existing heat-stress literature is substantial. The narrower potential contribution is a reproducible public-data sensitivity study showing how the association changes with missingness rules, FAOSTAT revisions and climate-data vintage; novelty has **not** been demonstrated by a systematic literature search.

**Method candidate:** Country-year panel, prespecified sample availability threshold and period, lag sensitivity, cluster-robust country uncertainty, year effects, alternative numerator/animal definitions; distinguish ecological association from causal animal physiology.

**Available source metadata, NOT downloaded observations:** FAOSTAT primary livestock milk/animal categories and annual coverage; World Bank CCKP historical CRU TS monthly/annual climate aggregates. Source links: https://www.fao.org/faostat/ ; https://data.fao.org/catalog/iso/f6a1fca8-3c0d-46a3-9aeb-3e81bbfd38c8 ; https://datacatalog.worldbank.org/infrastructure-data/search/dataset/0040276/climate-change-knowledge-portal-observed-climate-data-cru-ts4-07-0-5-degree .

**Data/rights gate:** Verify the exact FAOSTAT dairy-animal denominator availability, unit definitions, years, version, licence and API extraction; CCKP CRU TS4.07 metadata end in 2022, so do not imply a 2026 historical climate observation. Country-level climate cannot establish herd exposure. No proprietary herd data assumed. **Priority:** P2; **State:** DATA_DICTIONARY_PENDING / NOVELTY_UNVERIFIED.

## AGR-FUT-002 — Laying hens: egg-output measurement and poultry-stock denominator
**Precise question:** How sensitive are reported country-year egg-output-per-hen indicators to different FAOSTAT production and chicken-stock definitions, revisions and missing-data rules in a prespecified multi-country panel?

**Gap to verify:** Egg productivity has extensive prior research. An explicit audit of denominator and category alignment might be publishable as a data-quality note, but **no originality claim** is made until a targeted systematic source review.

**Method candidate:** Crosswalk national eggs-in-shell output, laying-hen stock where explicitly available, and total chicken stock as a *separately labelled invalid proxy*; compare sensitivity to using production-to-stock ratios and coverage. **Never call a total-chicken ratio hen-day egg yield.**

**Available source metadata, NOT downloaded observations:** FAOSTAT crop/livestock products include eggs; FAOSTAT live animals include chickens; actual layer-only series must be checked before any ratio is computed. https://www.fao.org/faostat/ ; https://data.fao.org/catalog/iso/f6a1fca8-3c0d-46a3-9aeb-3e81bbfd38c8 .

**Data/rights gate:** Confirm whether layer-specific population is openly reported for the target countries; otherwise stop at metadata comparison and do not fabricate a denominator. Check official data licence and release version. No poultry welfare, flock intervention or experiment implied. **Priority:** P2; **State:** DENOMINATOR_BLOCKED / NOVELTY_UNVERIFIED.

## AGR-FUT-003 — Pistachio: national yield variability versus observed climate
**Precise question:** Across pistachio-producing countries with reported harvested area and production, how does annual reported pistachio yield co-vary with seasonal temperature and rainfall anomalies, and how robust are associations to alternate crop-calendar windows and missingness thresholds?

**Gap to verify:** Climate–yield studies of pistachio already exist; any incremental value must be demonstrated by a transparent country-year data-vintage sensitivity design, not asserted as first-in-field.

**Method candidate:** FAOSTAT pistachio harvested area/production/yield series with unit checks, CCKP historical observed CRU TS climate, prespecified seasonal windows only where agricultural calendars are documented; country/year effects and uncertainty, no causal interpretation of annual aggregates.

**Available source metadata, NOT downloaded observations:** FAOSTAT crop production includes treenuts and harvested area/yield categories; World Bank CRU TS4.07 observed climate is publicly catalogued and available through API/XLS. https://www.fao.org/faostat/ ; https://datacatalog.worldbank.org/infrastructure-data/search/dataset/0040276/climate-change-knowledge-portal-observed-climate-data-cru-ts4-07-0-5-degree .

**Data/rights gate:** Confirm exact pistachio item code and countries, harvested-area reliability, climate aggregation matching actual production geography, version dates, and licence. National mean climate is not orchard exposure. **Priority:** P3; **State:** CODEBOOK_PENDING / NOVELTY_UNVERIFIED.

## Capacity and governance
Only these three subjects were advanced from the older requested catalog in this pass. The remaining catalog (broilers, aquaculture, cereals, other fruit/nuts, biotechnology, animal breeding, processing, fibres, gemstones, etc.) stays queued. No new paper enters active authorship until MR/AE/ZM gates and a defensible dataset/novelty check permit it. Human author identity, consent, approvals and research ethics are not inferred from topic selection.

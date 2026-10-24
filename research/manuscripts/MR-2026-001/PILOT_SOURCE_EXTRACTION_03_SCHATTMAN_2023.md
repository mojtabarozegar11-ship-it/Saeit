# MR-2026-001 — Candidate source QA 03: Schattman et al. (2023)

**Prepared:** 2026-10-24. **Status:** independent *targeted-discovery* source audit; **NOT** a systematically retrieved/included study. **Decision:** BORDERLINE — retain for citation chasing and boundary calibration, **not** evidence of farmer adoption of a deployed DSS.

## Bibliographic identity and evidence trail

Rachel E. Schattman, Haley Jean, Joshua W. Faulkner, Rebecca Maden, Lisa McKeag, Katie Campbell Nelson, Vernon Grubinger, Stephanie Burnett, M. Susan Erich, and Tsutomu Ohno (2023). *Effects of irrigation scheduling approaches on soil moisture and vegetable production in the Northeastern U.S.A.* Agricultural Water Management **287**, article **108428**. DOI: https://doi.org/10.1016/j.agwat.2023.108428.

- Source text (author-posted full article, consulted 2026-10-24): https://www.researchgate.net/publication/371851259_Effects_of_irrigation_scheduling_approaches_on_soil_moisture_and_vegetable_production_in_the_Northeastern_USA
- Bibliographic corroboration (EPA HERO): https://hero.epa.gov/reference/11280789/
- Author's contextual summary: https://rachel-schattman.squarespace.com/news/2023/6/25/new-article-effects-of-irrigation-scheduling-approaches-on-soil-moisture-and-vegetable-production-in-the-northeastern-usa
- Provenance: discovered through targeted public-web search, **not** Scopus/WoS/CAB export; source section/page pointers below refer to the author-posted text, not to an independently downloaded, checksummed PDF. No raw record export or DOI cross-check via a licensed bibliographic database was conducted.

## Evidence chart (candidate, not final)

| Domain | Source-anchored extraction | Evidence classification / limitation |
| --- | --- | --- |
| Study setting | Experimental research plots at University of Maine (2021, 2022) and University of Vermont (2019, 2021), not an observed rollout on independently managed commercial farms. See §2.2–2.3, printed pp. 3–4. | **M** field-measured trial outcomes; **NOT O** farmer adoption/adherence. |
| Irrigation interventions | Four arms: irrigation triggered by soil feel; irrigation when 30-cm soil tension reaches **20 kPa**; daily timer; no-irrigation control. Sensors logged soil conditions; treatment flow meters recorded applied irrigation weekly. See §2.3, p. 4. | Sensor/threshold-guided scheduling **is not automatically an analytical DSS issuing farmer-facing recommendations**. Code as `sensor_threshold_rule`, DSS status **unresolved/no documented deployed farmer-facing advisory interface**. |
| Outcome provenance | Water applied: recorded from flow meters (**M**). Crop yield/quality: harvested and recorded (**M**). Soil tension: instrument readings (**M**). Daily evapotranspiration: **modeled** with Climate Smart Farming Water Deficit Calculator (**P**), not direct measured ET. See §2.3–2.4, p. 4. | Never label modeled ET as measured, or infer total water savings from ET modeling. |
| Field comparisons | Authors report sensor treatment used less irrigation than soil-feel method in **three of four site-years**; **no statistically significant yield effect** of scheduling method overall. Sensor scheduling yielded more days in the preferred soil-moisture band. See §4 Conclusion, pp. 13–14. | **M** comparisons in experimental plots; no pooled saving rate extracted or inferred. Avoid claiming benefit in all site-years. |
| Farmer perspectives | Survey of **155 respondents** and **four focus groups with 22 participants**; pre/post questionnaire subset **13**. See §2.1 and §3.1. Farmers reported costs and cloud-data access concerns; willingness to use/invest was discussed. | **S** reported perceptions and intentions. **Not** measured sustained uptake, DSS adherence, or realized farm profits. Distinguish survey denominator (155), focus group attendees (22), and questionnaire subset (13). |
| External validity | Field trials occurred in years with **above-average precipitation**; researcher-operated plots and regional self-selected survey participants limit transfer to water-scarce, farmer-operated settings. See §4, p. 13 and §2.1. | Do not present as direct validation **under demonstrated water scarcity**. |
| Economic outcomes | Surveyed hypothetical willingness to invest given potential yield improvement; no verified farm-level DSS return-on-investment estimate extracted. | **S**, hypothetical preference, **not** observed economic impact. |
| Adoption outcomes | Survey opinions and workshop intentions; no demonstrated multi-season farmer uptake of the experimental scheduling protocol. | Adoption stage = **interest/intention**, not sustained adoption. |

## Key methodological distinction discovered

This source is particularly useful as a **negative-control/boundary example**. A randomized plot-level field experiment can establish real biophysical outcomes while *not* establishing that an analytical DSS was deployed to farmers or adopted by them. Conversely, a farmer survey can establish preferences without measuring sustained technology use. A review combining these into a single 'field-validated and adopted DSS' count would introduce construct misclassification.

Proposed coding: separate `measurement_instrument` (tensiometer, sensor), `decision_rule` (fixed 20-kPa trigger), `DSS_recommendation` (not demonstrated), `decision_actor` (research team vs grower), and `adoption_followup` (none documented). Maintain independent outcome provenance M/O/S/P/U for each extracted endpoint.

## Provisional eligibility adjudication — pending protocol freeze

- **Strict farmer-facing DSS question:** **exclude from main included-study set** if final eligibility requires an actual DSS recommendation used by farmers, because the field component tests threshold-guided research plots and the farmer component captures views, not uptake of a deployed DSS. Confirm from final full text before decision.
- **Broad sensor-assisted scheduling/decision-cue question:** **potentially include in a separately labeled 'sensor/threshold field validation' stratum**, explicitly without farmer-adoption attribution.
- **Citation-chasing/reference role:** retain regardless of strict eligibility to avoid missing comparisons between real measured outcomes, sensor systems, and farmer perceptions.
- This is a **pre-screening proposal**, not a recorded screening vote, inclusion count, or human-review decision.

## QA / unresolved items

1. Verify publisher-version pagination and numerical irrigation volumes against the original tables before extracting quantitative effects.
2. Independently check that all relevant irrigation and crop measurements were recorded at the stated unit of analysis; do not conflate four site-years with four independent farms.
3. Confirm whether any deployed decision-support software actually generated recommendations to farmers; mere cloud logging is insufficient.
4. Record wet-year context and external-validity limitation in any future narrative synthesis.
5. Verify licensing and use short paraphrases rather than reproducing figures or copyrighted tables.

**Scientific integrity:** No new experimental data, author contact, licensed-database search, PRISMA count, final eligibility vote, peer review, manuscript submission, or DOI creation is claimed by this audit.

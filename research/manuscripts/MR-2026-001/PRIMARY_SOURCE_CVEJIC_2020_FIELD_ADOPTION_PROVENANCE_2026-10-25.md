# MR-2026-001 — primary-source extraction, Cvejić et al. (2020)

**Version:** 2026-10-25 source-extraction v1; not a human screening determination and not a final review result. **Primary-source access:** official journal article HTML inspected on 2026-10-25.

Citation: Cvejić, R., Černič-Istenič, M., Honzak, L., Pečan, U., Železnikar, Š., & Pintar, M. (2020). *Farmers Try to Improve Their Irrigation Practices by Using Daily Irrigation Recommendations—The Vipava Valley Case, Slovenia.* Agronomy, 10(9), 1238. **Publisher-verified DOI:** https://doi.org/10.3390/agronomy10091238  
Official text: https://www.mdpi.com/2073-4395/10/9/1238 (publisher's HTML, no unverified PDF page references).  
Bibliographic search provenance: original OpenAlex result `W3080741464` in `index_search_2026-10-25/OPENALEX_EXECUTED_SEARCH_2026-10-25.json`; candidate in metadata worklist `CANDIDATE_QUEUE_604_METADATA_TRIAGE_2026-10-25.csv`. **This is a candidate, NOT a study formally included by human screening.**

## Question and design
- **Scope:** farmer-facing irrigation decision-support recommendations, real farms, longitudinal implementation process; candidate for protocol primary analytical stratum A.
- **Area and crop context:** Vipava Valley, Slovenia; heterogeneous agricultural holdings; the project began in 2016 and follow-up includes 2017–2020. The journal reports 35 interested farms from the initial participation call; this is not a randomized sample. The paper reports agricultural parcel participation and farm practices, no experimentally randomized system-level efficacy inference.
- **Intervention:** near-real-time soil moisture, precipitation/evapotranspiration forecasts and predicted phenology; web dashboard plus emailed daily irrigation advice including five-day recommendations. Operator/farmer decides whether to implement; not equivalent to a wholly autonomous closed-loop controller. Source: **Methods, sections 2.1–2.3**.
- **Data:** baseline structured farmer interviews, demonstrations and workshops, irrigation diaries (known nonresponse), questionnaire and recurring telephone conversations in 2020. Device/water-balance modeling also appears; carefully separate survey-reported actions from field-metered outcomes.

## Extracted evidence with source anchors

| Construct | Exact study claim (paraphrased) | Evidence type | Locator and limitation |
| --- | --- | --- | --- |
| Participating units | 35 farms were initially interested in programme enrolment; heterogenous crops | Enrollment, not retention or outcome | Article abstract and Methods §2.1; detailed attrition/response denominator requires checking |
| Uptake infrastructure | Daily irrigation recommendations supplied through email and website, and some farmers used them | Exposed advice / usage self-report | Methods §2.2–2.3 and Results §3; no independent web-service use logs shown for all farmers |
| Survey uptake | 83% **reported** use in 2020; 71% **reported** regular inspection of soil-moisture status | S: farmer self-report, survey/telephone feedback | Results §3, paragraph starting "All farmers provided feedback..."; do not convert into an externally observed uptake rate |
| Claimed behavior | 49% said irrigation duration unchanged; 40% said they irrigated more frequently but for shorter durations | S: farmer self-report | Results §3 same paragraph; no verified applied-water savings from these answers |
| Satisfaction | 66% said very satisfied; 6% (two farmers) dissatisfied | S: farmer-reported satisfaction | Results §3; satisfaction is distinct from observed adoption and measured field efficacy |
| Data completeness | About 91% did not keep regular irrigation diaries in the initial monitoring period | U / measurement limitation | Results §3 baseline paragraph; incomplete implementation logs prevent confident quantitative behavior verification |
| Scenario impact | Conditional **simulations** predicted 25% lower total irrigation volume and 24% lower energy and CO₂ emissions under specified irrigation strategy | P: modeled counterfactual | Abstract and §2.3 / Discussion; **NOT** measured post-deployment savings |
| Long-run adoption | Authors observe partial progression toward DSS-assisted decisions but note uncertain development after programme closure | Limited multi-year study-supported exposure, not definitive sustained independent adoption | Results §3 and Conclusions §5 |

## Source-integrity discrepancy requiring verification

The accessible publisher HTML says: **"Forty-six farmers use the irrigation advice they receive by e-mail"** while the original study description states **35 interested farms**. We cannot reconcile these numbers from the available narrative. It may be a typographical error, a denominator shift, or an unexplained participant count; **do not silently transform the source's "Forty-six" into "46%"**. Flag as a source-text discrepancy and seek an erratum / author clarification or table-anchored documentation. Do not use that figure in quantitative synthesis.

Percentages of 83%, 71%, 49%, 40%, 66%, 6% are source-reported; the exact denominator for each question is not independently validated and rounding to whole numbers should not be presented as independently enumerated farmers. The 6% (two farmers) may reflect a denominator near 33–35, but do not assign one without explicit data.

## Bias and validity cautions

Voluntary enrollment, mixed crops and management, technology co-interventions (sensor installation and training), repeated support from research staff, incomplete diaries, interview reliance, unblinded self-reports and the absence of a randomized control group limit causal interpretation. Irrigation requirements computed via the IRRFIB model and modeled energy/CO₂ differences are not independently metered farm treatment effects. The long implementation timeline does not automatically establish post-intervention autonomous or multi-season voluntary adoption, since researcher support was ongoing.

**Preliminary eligibility:** candidate A based on human-facing advice in production settings; human title/abstract and full-text screening must confirm. No formal inclusion or exclusion decision recorded here.

## Integration into manuscript (original prospective analytical note)

The Cvejić case demonstrates why descriptive data charts for scoping reviews must be multi-layered: availability and reception of advice; recalled/reported frequency of use; verified applied actions where measured; independent outcome measurements; and counterfactual model predictions. The source's reported farmer behavior is informative for implementation and sociotechnical barriers, while the prominent percentages for water, energy, and carbon are simulated scenarios rather than realized post-deployment gains. These constructs are recorded separately in the approved primary/context strata.

**Author contributions:** This file is an AI-assisted preliminary source extraction, not independent fieldwork by Mojtaba Roozegar and not a claim of co-authorship on the source article.

**Next:** find publisher correction/erratum for the "Forty-six" discrepancy, locate participant flow and unit denominator directly, human eligibility adjudication, source-anchored data charting, add to narrative only after eligible review conduct. **Journal submission: NOT SUBMITTED.**

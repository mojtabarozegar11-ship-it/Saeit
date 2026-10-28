# MR-2026-001 — fourth targeted source audit: IrrigaSys post-evaluation (Darouich et al., 2024)

**Audit date:** 2026-10-24  
**State:** targeted source-based *pilot* charting and critical appraisal; **NOT** a formally retrieved/scored systematic-review record, independent dual extraction, novelty proof, or final inclusion decision. Original publisher landing page returned HTTP 429 to direct retrieval in this session; publisher-indexed text and the University of Lisbon publication record / open-access repository indexed text were checked. The PDF's complete tables, appendices and figure images have **not** been independently inspected. Recheck them before final extraction.

## Bibliographic identity and trace
- Darouich H, Simionesei L, Oliveira AR, Neves R, Ramos TB. *Assessing the Impact of IrrigaSys Decision Support System on Farmers' Irrigation Practices in Southern Portugal: A Post Evaluation Study*. **Agronomy**. 2024;14(1):66. DOI: https://doi.org/10.3390/agronomy14010066
- Publisher: https://www.mdpi.com/2073-4395/14/1/66 (publisher-indexed sections: abstract, §2.1 Materials and Methods, §3.1–3.2 Results, §4 Conclusions, Table 1/2 captions and entries).
- University of Lisbon research record: https://researchportal.ulisboa.pt/en/publications/assessing-the-impact-of-irrigasys-decision-support-system-on-farm/
- University repository and accessible PDF location (file itself needs full visual inspection): https://repositorio.ulisboa.pt/entities/publication/874f83da-cbc2-4742-99f6-b7ce1543a000 ; https://repositorio.ulisboa.pt/server/api/core/bitstreams/f22a324c-bbce-4962-8bca-a59c75961c02/content
- Related *different* earlier IrrigaSys system-description paper (not the post-evaluation): Simionesei et al. (2020), https://doi.org/10.1016/j.compag.2020.105822 . Do not count as an independent deployment outcome without verifying distinct data.

## Why this record changes the novelty assessment

This is a close *primary-study* match to the proposed review's central question: farmer-facing irrigation DSS recommendations, actual farmer schedules and post-evaluation of alignment with model schedules under different precipitation conditions. Therefore the mere juxtaposition of “field deployment + farmer adherence + water scarcity” **cannot be claimed as a novel idea**. Any eventual review must identify an unaddressed, cross-study methodological question (for example, separately coding real recommendation exposure/adherence, actual measured irrigation, modeled yields, and verified farm profit) and compare it with the scopes of earlier reviews.

## Verified from source-indexed methods/results (with source provenance)

| Dimension | What the source reports | Coding caveat |
|---|---|---|
| Setting | Sorraia Valley irrigation district, southern Portugal, with dry/semiarid conditions and irregular rainfall. | Water-constrained agricultural setting; do not assert every plot experienced measured drought. |
| Service operation | IrrigaSys provided weekly optimized irrigation advice, but farmers decided whether to follow it. Service operated in 2017–2022. | Farmer-facing actionable DSS = **DSS_ACTIONABLE**; availability of advice ≠ measured adherence. |
| Overall reach | About **30 farmers**, **103 plots**, **2,080 ha** supported annually according to Methods §2.1. | Service coverage, **not** the analytic sample and **not** 30 independently observed adopters. |
| Evaluation sample | **20 maize plots**, center-pivot irrigation, compared for **2019** (dry) and **2022** (average/wetter). | Repeated plot-year comparisons, not 40 independent farms or a randomized trial. |
| Intervention contrast | Actual farmer-defined irrigation schedules versus **MOHID-Land optimized schedules** recommended by DSS. | Observed/recorded schedules vs counterfactual model recommendation, **not** randomized DSS treatment/control. |
| Irrigation volumes | Published average farmer/model irrigation volumes: **7,800 / 8,650 m³ ha⁻¹ in 2019** and **7,940 / 7,800 m³ ha⁻¹ in 2022**, respectively (Results §3.1). | Values are published descriptive aggregates; do **not** claim a measured intervention water-saving percentage or a causal benefit. In 2019, model-recommended mean is higher than farmer mean. |
| Crop yield | Paper explicitly states crop yields in **both** farmer-schedule and model-schedule comparisons were **estimated with MOHID-Land**, using the respective schedules. | **P** for estimated yield, not directly measured harvest yield; pest/disease effects excluded. |
| Economic outputs | Price-based indicators calculated from modeled yield and an assumed maize price of **EUR 0.26/kg**; variable operation/maintenance/labor/energy costs not included. | **P** modeled gross value/productivity, **not** independently measured profit, net returns or cost savings. |
| Adoption/adherence | Authors compare farmer irrigation schedules to DSS advice, and discuss the effect of precipitation forecasts on deviations. | **O?** recorded scheduling decisions; **do not infer** recommendation opening, per-advice adherence rate, voluntary independent uptake, or multi-year retention from service longevity alone. |
| Bias/limits | Shallow groundwater upward fluxes omitted by the 1D model, affecting model-versus-farmer comparisons; precipitation forecasts unreliable, especially wetter season. | Potential model misspecification and differential measurement validity; must be reflected in synthesis. |
| Data access | Data availability statement: data available on request from corresponding author. | Raw plot-level schedule and actual metered irrigation series not independently obtained in this audit. |

**Provenance coding:** `M` = independently documented field instrument measure; `O` = observed or recorded decision/use; `S` = self-report; `P` = model-derived/predicted/counterfactual; `U` = not independently established. The published analysis mixes recorded farmer schedules with **P** outcomes; water-use figures should be tagged **recorded-schedule/model-computed unless raw metering is verified**, not assumed M. Assign provenance per endpoint, not once for the paper.

## Important year-label inconsistency to resolve, not silently normalize

- The **abstract** in the publisher and university records states **2019 and 2020** (2019 driest; 2020 average).
- The **Methods §2.1**, **Results §3**, Figures 4–5, and Table 2 in the publisher-indexed body consistently discuss **2019 and 2022**.
- The title and DOI are the same source. This is a documented **within-publication inconsistency**; do not automatically “correct” the publisher abstract or assert an official erratum. Check the full PDF and any version notes; if still unresolved, seek clarification from the corresponding author. Use **2019/2022 as body-described analysis years, with an explicit discrepancy flag** in the working extraction.

## Research integrity / causal-inference safeguards

1. The system's reported 2017–2022 operation is not equivalent to longitudinal observation of each of the 20 sampled plots or retention of each user for six years.
2. The 20 selected maize plots are a *purposive* subsample of 103 serviced plots. Selection, missingness and representativeness require full-text examination.
3. Comparing a farmer schedule with a mathematically optimized counterfactual schedule does **not** establish that the DSS caused actual water savings or increased income.
4. Farmers' model-based productivity can appear high/low due to unmodeled capillary rise, weather forecast error, or hypothetical yield response. These are not directly observed harvest effects.
5. The MCA rankings depend on criterion weights (water priority vs economic priority), and its `U` scores are **unitless preference indices**, not physical water saving or money.
6. The work includes two seasons in its evaluation, but does not by itself verify adoption intention, recommendation click-through, adherence per advice, or sustained autonomous uptake.

## Pre-freeze screening / extraction decision

- **Discovery relevance:** high. **Final eligibility:** PENDING independent screening under a frozen DSS definition and protocol.
- If eligible, split endpoints into: (a) DSS service reach; (b) farmer schedule data; (c) model-optimized schedules; (d) modeled yield/water productivity; (e) model-based economic indicators; (f) actual adoption/adherence observations (not established by this audit).
- Need: full publisher PDF/figures, raw data or clarification on volume measurement, study sample inclusion, 2019/2020 vs 2019/2022 discrepancy, and second human reviewer.
- Add this record to the **prior-study overlap matrix** before asserting that the proposed review uniquely addresses observed farmer behavior.

**Status boundary:** This is a single *targeted discovery*, not a Scopus/WoS/CAB query; no new PRISMA search counts, included-study total, measured savings, peer review or publisher submission is claimed.

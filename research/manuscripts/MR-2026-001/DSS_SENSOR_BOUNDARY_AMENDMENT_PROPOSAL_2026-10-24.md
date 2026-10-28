# MR-2026-001 — DSS-versus-sensor eligibility amendment proposal (v0.1)

**Prepared:** 2026-10-24. **Status:** PROPOSED amendment to `SEARCH_EXECUTION_PLAN.md`; **not frozen, not author-approved, and not retrospectively applied to any database records**.

## Why this amendment is necessary

The targeted source check of Schattman et al. (2023), DOI https://doi.org/10.1016/j.agwat.2023.108428, revealed a construct-validity problem: a sensor-triggered experimental irrigation treatment with measured field outcomes is not necessarily a deployed decision-support *system* adopted by farmers. The paper also contains farmer interviews and intentions, but these do not show adoption of the experimental system. In contrast, the already charted Amini et al. (2025) study concerns a participatory farmer-facing DSS pilot. If pooled indiscriminately, these distinct evidence types would overstate adoption and efficacy.

## Proposed intervention taxonomy (mutually exclusive for primary system type)

| Code | Operational criterion | Review handling |
| --- | --- | --- |
| `DSS_ACTIONABLE` | Named algorithm/software/service generates an actionable irrigation timing, depth, allocation or schedule recommendation; record whether farmer receives/uses it. | Candidate for main DSS stratum **only if field or farmer-facing evidence meets other criteria**. |
| `RULE_THRESHOLD` | Fixed sensor/soil/water threshold initiates irrigation, with no documented analytic advisory software. | Separate field-validation stratum; **not** counted as analytical DSS adoption. |
| `MONITOR_ONLY` | Soil-moisture, weather, satellite or IoT dashboard displays measurements without a documented actionable irrigation recommendation. | Exclude from strict DSS synthesis; retain as contextual comparison if relevant. |
| `AUTOMATION_ONLY` | Timer/actuator performs predefined watering without a recommendation or decision logic tied to crop-water need. | Exclude from strict DSS synthesis; may be a comparator. |
| `SIMULATION_ONLY` | Optimizer/DSS assessed only in silico or by counterfactual model, with no real DSS-guided farm deployment. | Exclude from field-validated efficacy stratum; use for context, not measured savings. |
| `UNCLEAR` | Source does not establish what the tool actually outputs or who uses it. | Request full-text clarification; do not assume eligibility. |

**Avoid an overly narrow software definition:** a documented farmer-facing, rule-based advisory service can qualify as `DSS_ACTIONABLE` when it actually issues an actionable recommendation. Classification must follow *function and delivery*, not marketing label, sophistication or hardware brand.

## Separate evidence axes — do not merge them

1. **Deployment actor:** farmer/grower; adviser; researcher; autonomous system; not reported.
2. **Decision use:** recommendation generated; recommendation delivered; use observed; adherence quantified; follow-up documented; unknown. Each is separately coded.
3. **Adoption stage:** awareness/interest; intention; supervised pilot use; voluntary ongoing use; multi-season sustained use; independent diffusion; not reported. Interest and intention never count as observed adoption.
4. **Endpoint provenance:** `M` instrument-measured farm/plot outcome; `O` directly observed decision/use; `S` respondent self-report; `P` simulation/prediction; `U` not verifiable. Assign **per endpoint**, not per paper.
5. **Comparator:** pre-post; concurrent randomized; concurrent nonrandomized; historical; model counterfactual; none. Record actual unit (plot, farm, farmer, season), duration and denominator.
6. **Water-constraint context:** observed physical scarcity/drought; institutional allocation constraint; author-stated scarcity without measurements; no demonstrated constraint; not reported. Do not infer drought from a generic paper title.
7. **Economics:** actual recorded expenditure/revenue; modeled cost-benefit; hypothetical willingness-to-pay; qualitative cost barrier; not reported.

## Three examples used for calibration, not eligibility decisions

- **Amini et al. (2025)**, https://doi.org/10.1038/s41598-025-26567-z: participatory irrigation DSS and observed farm data; verify each outcome, baseline, farmer-use observation and duration independently. No assumption of sustained adoption.
- **Silvestri et al. (2025)**: distinguish measured historical field inputs from *simulated* DSS savings; see `PILOT_SOURCE_EXTRACTION_02_SILVESTRI_2025.md` and Table 3 QA note. Do not promote a simulated benefit into M.
- **Schattman et al. (2023)**, https://doi.org/10.1016/j.agwat.2023.108428: plot-level sensor threshold and recorded irrigation; farmer perceptions separate; strict DSS eligibility unresolved pending protocol choice. See `PILOT_SOURCE_EXTRACTION_03_SCHATTMAN_2023.md`.

## Search sensitivity implication

Retain the broad irrigation scheduling/sensor terms in the **discovery search**, so that relevant farmer-facing rule-based advice is not missed. Apply the taxonomy during documented title/abstract/full-text screening, not by silently excluding all sensor papers at query time. Before freeze, test recall against all three calibration studies and at least two earlier reviews; document whether each paper is indexed in each licensed database and why a query did or did not retrieve it.

## Human decision gate

A qualified human author and an independent information specialist must decide whether the review asks about (A) deployed **farmer-facing DSS**, with sensor-only work as a contextual comparator, or (B) the broader universe of **technology-assisted irrigation decision cues**, with DSS, sensors and timers stratified and no joint adoption claims. Choice A is provisionally better aligned with the working title, but **not approved**. After approval, freeze PCC, exact queries and eligibility rules *before* formal searches; any subsequent changes require an explicit dated amendment.

**State:** no licensed Scopus/WoS/CAB searches, exports, screening votes, included-study counts, manuscript or journal submission occurred as part of this document.

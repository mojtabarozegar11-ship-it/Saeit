# MR-2026-001 — separate adversarial AI internal review, SANRA v2019

**Date:** 2026-10-25. **Article reviewed:** `MR-2026-001_DISCOVER_AGRICULTURE_PERSPECTIVE_AUTHOR_REVIEW_CANDIDATE_2026-10-25.md` (updated after its Car numerical-provenance correction). **Reviewer:** ChatGPT, an AI quality-control pass separate from manuscript drafting; **NOT** an external independent human peer review, certification, or publisher acceptance. **Decision:** MAJOR REVISION / NOT CLEARED FOR JOURNAL SUBMISSION.

## Scale and evidence
The original [SANRA paper](https://doi.org/10.1186/s41073-019-0064-8) identifies six 0–2 items; SANRA is a **critical appraisal scale**, NOT a compliance certificate or publishing threshold. Scores below are provisional, author-accessible assessments, not externally calibrated human inter-rater ratings.

| SANRA item | Provisional AI score /2 | Manuscript evidence and independent objection |
|---|---:|---|
| 1. Importance to readers | **2** | Introduction identifies a real inferential error: conflating irrigation advice, uptake and measured savings. Prior-art caveat included. |
| 2. Concrete aims | **2** | Abstract and methods specify claim-level evidentiary distinctions M/O/S/P/U and eight contrasting empirical contexts. |
| 3. Literature search description | **1** | Purposive selection criteria and eight included primary papers are declared, but exact database-by-database queries, search dates, retrieval decisions and documented exclusion rationale have **not** been preserved sufficiently to assess ascertainment. Do NOT invent systematic-review flow counts or retrospectively claim prospective search. |
| 4. Referencing | **1** | Sixteen traceable DOI references and in-text citation numbering exist; several source titles/full methodological details (Elia, Baroni, Lorite, Mabhaudhi, Umutoni) remain unverified at full-text level and some bibliographic details may need Crossref/publisher checking. |
| 5. Scientific reasoning | **2** | Explicit rejection of misleading causal/metrological claims, narrow novelty claim and alternative explanations for nonadherence. This score does not prove novelty, originality or suitability to editors. |
| 6. Relevant outcome data | **1** | Physical, modeled and self-reported endpoints are distinguished; source-level Amini F7 inconsistency, conditional Cvejić denominator and Car Table 5 text mismatch are flagged. Missing metering details, inaccessible full methods and no harmonized advice-event denominator preclude stronger claims. |
| **Provisional total** | **9/12** | The numeric sum is an *internal prioritization aid* and is **not** permission to submit or a guarantee of quality or acceptance. |

## Specific scientific corrections / decisions

1. **Car (2012) internal table inconsistency is unresolved.** The coauthor-uploaded machine-readable Table 5 lists group counts 26+7+3+6+15+17=74, versus printed 72. Do not call this confirmed author error before seeing the source page image. Independently, the publisher abstract coherently separates 45 all-season, 13 half-season and 14 never-returned participants =72. The latter is a **return-data duration count**, not independently metered recommendation-specific adherence. The new pure-Python audit `analysis/claim_level_source_arithmetic_audit.py` preserves the arithmetic and this caveat.
2. **Amini (2025) F7 conflict remains an unresolved published discrepancy**, not a revised measurement: Table 5 displayed productivity treatment 4.6, control 6.0 (difference -1.4), whereas the publisher conclusion gives -0.1. The field-depth contrasts F5=-253.6 mm and F7=+292.7 mm are differences between published rounded comparators, not causal generalizations.
3. **Cvejić (2020) 83% farmer use is survey evidence.** A common n=35 can mathematically generate eight rounded percentages and the two-respondent 6%, but does not establish the actual 2020 sample base or harmonize 2019's 46 advice recipients. Modeled 25% volume / 24% energy savings are not metered adoption outcomes.
4. **Novelty risk is high.** Lorite (2012), Car (2012), Baroni (2019), Ara (2021), Bounajra (2024) and Wei (2024) already cover aspects of farmer compliance, advice/action differences and adoption. Avoid 'first ever'; frame any contribution as a *worked source-level epistemic audit*, and ask the human author to decide whether this is substantively enough for a Perspective.
5. **No broad rate of failure or magnitude of savings.** Eight purposively selected and partly abstract-accessed cases cannot establish prevalence, pooled effect, counterfactual benefit or inter-coder reliability of the proposed M/O/S/P/U rubric.

## Mandatory closure gates

- [ ] Confirm publication-quality provenance for the full-page Car Table 5; if access fails, retain explicit U and omit disputed counts.
- [ ] Add a transparent, dated, reproducible *non-systematic* discovery log with queries actually performed, inclusion rationale, and recognized search omissions. Never invent search counts or a PRISMA process.
- [ ] Verify any quantitative claim dependent on restricted full-text methods or downgrade it to publisher-abstract-only uncertainty.
- [ ] Confirm that the proposed six-link claim-to-evidence method is genuinely incremental relative to Ara, Lorite, Car, Baroni and existing reviews; revise or withdraw unsupported novelty.
- [ ] Remove internal workflow instructions, editorial self-referential language and placeholders from the **submission version** while keeping them in a separate author-approval dossier. Manuscript currently contains [AUTHOR ...] placeholders and commentary that should not be transmitted to a journal unchanged.
- [ ] Obtain real scientific input and accountable substantive revision by the intended human author Mojtaba Roozegar; verify truthful affiliation, funding, COI, AI disclosure, ethics, data availability, originality, third-party rights, journal/article type/APC and final text.
- [ ] Produce and validate a clean, journal-format manuscript + cover letter, check the journal portal, acquire explicit manuscript-specific approval **before** any actual submission.

## Publisher policy source
[Discover Agriculture original submission guidelines](https://link.springer.com/journal/44279/submission-guidelines) requires an abstract under 250 words, a cover letter, a funding declaration, a data availability statement, authorship and conflict declarations, and describes **Perspective** as a narrow scholarly discussion distinct from a comprehensive **Review**. Its online submission service is Snapp. A clean Perspective is plausible but **not yet editorially accepted or formally approved by the author**.

**Disposition of this cycle:** internal review decision **major revision**; no final QC exit, no manuscript submission, no Manuscript ID, no journal peer review and no publication. Start or continue the next paper only with a distinct question and genuine data/source path; preserve the queue without sacrificing quality.

# MR-2026-001 — original-source adjudication and executed full-file QA (C126)
Date: 2026-10-30. R-01 research-only branch. Source manuscript: [C125](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/MR-2026-001/MR-2026-001_C125_F5_UNIT_SOURCE_ADJUDICATED_AUTHOR_REVIEW_MANUSCRIPT_2026-10-30.md); source matrix: [C125 ledger](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/MR-2026-001/MR-2026-001_C125_SOURCE_CLAIM_MATRIX_2026-10-30.tsv).

## Reproducible checks executed in-memory on the complete GitHub files
The full 66,304-character manuscript and 7,396-character TSV were fetched from GitHub and evaluated in JavaScript (not Python). This is structural/source-text QA, **not** independent peer review or source-data validation.

- PASS — manuscript_has_full_sections
- PASS — narrative_review_declared
- PASS — reference_count_25
- PASS — ledger_row_count_13
- PASS — ledger_unique_ids
- PASS — ledger_full_schema
- PASS — ledger_all_cells_nonempty
- PASS — ledger_sources_https
- PASS — no_todo
- PASS — F7_rounding_boundary_present
- PASS — F5_percent_column_nonpooling

**Result: 11/11 checks passed.** No structural check failed. The matrix contains 13 claims; 8 source evidence rows carry BLOCKED statuses: C120-02, C120-03, C120-04, C120-06, C120-07, C120-08, C123-10, C124-12. No author-approved release manifest or independent original-source correction was provided; **BLOCK_SUBMISSION**.

## Two original-publication discrepancies adjudicated without inventing a correction

**Car et al. (2012):** Institutional abstract gives 45 all-season input senders + 13 half-season + 14 never = **72** trial irrigators. The author-uploaded article Table 5 gives category counts 26+7+3+6+15+17 = **74**, despite printing total 72. Table 6 gives 11+10+9+8+3 = **41** categorized responses, whereas surrounding prose references 40 respondents. These are non-interchangeable respondent frames. **Resolution:** retain the 45/13/14 partition only as *reported SMS input participation*; exclude Table 5 and Table 6 from any respondent prevalence estimate or pooled adherence effect. This resolves the editorial inference, **not** the original roster. Sources: https://rune.une.edu.au/entities/publication/68f9d1ef-6e62-415a-b831-0beb96df9853 ; https://www.researchgate.net/publication/257018309_Using_a_mobile_phone_Short_Messaging_Service_SMS_for_irrigation_scheduling_in_Australia_-_Farmers%27_participation_and_utility_evaluation

**Amini et al. (2025):** Original publisher Table 4 displays F7 irrigation-input WP **4.6** versus **6.0 kg/m³** (DSS versus control), giving a displayed difference of **−1.4 kg/m³**. The narrative alternatively gives **−1.3**, **−1.4** and **−0.1 kg/m³** across passages. One-decimal rounding permits approximately −1.50 to −1.30 for the true subtraction; **−0.1** cannot be reconciled by ordinary rounding. Table 5's F7 −3.22 and F5 +3.87 under a percentage heading are not the conventional relative changes computed from Table 4 (F7 −23.33%, F5 +82.61%). **Resolution:** quote no unique F7 numerical treatment effect, do not pool the percentage column, and preserve the original qualitative direction (F7 applied irrigation increased by 292.7 mm; reported irrigation-input WP decreased). Underlying unrounded records and author clarification remain missing. Source: https://www.nature.com/articles/s41598-025-26567-z

## Manuscript-safe replacement paragraph for the human editor
> Car et al. (2012) reported 72 trial participants with a 45/13/14 SMS-input participation partition, but their Table 5 and Table 6 category totals cannot be reconciled with the corresponding printed respondent frames; these categories were therefore excluded from prevalence estimation. Amini et al. (2025) reported higher applied irrigation depth and lower irrigation-input water productivity for F7, while its exact water-productivity contrast and percentage-column interpretation remain inconsistent across the published tables and prose. Neither case supports a quantified pooled adherence or causal water-saving estimate.

## Publication decision
- **READY_FOR_REVIEW:** source-safe paragraph and arithmetic exclusion rule usable in human editorial review.
- **BLOCKED:** authenticated Car roster/erratum, Amini raw F7 values/clarification, remaining ledger blockers, independent scholarly review, author approval and journal-specific requirements.
- **NOT SUBMITTED / NOT ACCEPTED / NOT PUBLISHED.** No production site, factory, master-agent, or payment actions.

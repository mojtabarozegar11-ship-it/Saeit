# AE-2026-001 — internal AI adversarial review and human-author decision delta after C30

**27 October 2026.** This is a critical assessment by an AI research assistant, **not** a human referee, author certification, editorial decision, or submission approval.

## New independently computed material this cycle

1. **Baseline-availability selection in observed 2019 levels:** the 153 complete 2000/2019/2023 economies have median 2019 agricultural value added per worker $6,237.919; the 16 with 2019/2023 observations but no positive 2000 baseline have median $2,840.965. Pooled pairwise probability that an added economy exceeds a complete-case economy is 868/2448 = 0.354575. This does **not** identify why 2000 data are missing.
2. **Observed 2019–2023 absolute growth volatility:** median absolute annual log growth 2.316370 log-pp/y (153) versus 4.759665 (16). Absolute annual growth >10 log-pp/y occurs in 9/153 versus 2/16; CAF and DJI are the two latter cases. This is a different question from the earlier C19 *signed mean influence* analysis.
3. **Regional sensitivity of level selection:** within-region pairwise probability is 191/461 = 0.414317, rather than the pooled 0.354575; Sub-Saharan Africa alone is 0.559524. This shows sensitivity to regional composition, not proof of a causal missingness process.

**Provenance:** official 2026-only WDI panel in the GitHub research branch, blob d4910ff78219f9e5097c6301a6fbfa7752bbf4f9; [C30 methods and computations](../manuscripts/AE-2026-001/AE-2026-001_C30_2000_BASELINE_MISSINGNESS_2019_LEVEL_AND_VOLATILITY_SELECTION_2026-10-27.md). These findings were integrated into the [consolidated English author-review manuscript](../manuscripts/AE-2026-001/AE-2026-001_CONSOLIDATED_AUTHOR_REVIEW_MANUSCRIPT_2026-10-27.md), Methods 2.8 and Results 3.6. C13/C14 were reread to reconcile cohort counts: 217 nonaggregate total, 153 mask 111, 16 mask 011, four mask 110 and one mask 100.

## Adversarial assessment: what would a skeptical reviewer object to?

- **Not a missing-at-random test.** No mechanism, regression model or causal attribution of missing baseline values was identified.
- **Non-comparable regions and tiny added cohort.** Within-region comparisons differ from pooled, and two regions have only two added economies. No p-values or global confidence intervals are asserted.
- **Mathematical coupling.** The 2019 level enters the denominator of 2019–2023 growth. Association between 2019 level and growth cannot be interpreted as a structural economic effect.
- **Sample conflation risk.** C30 is 2026-only (153+16), not the primary 155-economy 2024/2025/2026 historical-vintage fixed panel. It must not be described as a revision across releases.
- **Prior art and data provenance remain open.** No newly archived 2024/2025 ILOSTAT worker tables, historical direct `countryatlas::compare_vintages` benchmark, independent worker census, original estimator or verified journal novelty was produced in this cycle.

## Human-author release decision

**AE:** MAJOR REVISION / NO SUBMISSION. A revised English author-review manuscript exists, but no newly verified source-aligned Word artifact is asserted by this packet. The human author must validate scientific contribution, exact final version, affiliation/identity, all references, funding, conflicts, AI assistance, data rights, journal/APC and cover letter before any journal submission.

**MR:** MAJOR REVISION / NO SUBMISSION. Car publisher Table 5, remaining Amini F7 discrepancies, Cvejić denominator, complete comparator methods and empirical G/D/R/A remain open.

**ZM:** DATA REBUILD / NO SUBMISSION. Original integer counts, exact compatible v2.0 FASTA/GTF, read MD5, multimapping and experimental-unit independence remain open; FPKM and 1,167 exploratory candidates are not independently confirmed DEGs.

**Actual transitions to human-approved/submitted/peer-reviewed/accepted/published:** 0/3. **Website:** GitHub staging only; no live deployment; PR #1054 stays draft/unmerged; no restricted social account interaction. No money, VPS use or 149.54 GB FASTQ bulk download.

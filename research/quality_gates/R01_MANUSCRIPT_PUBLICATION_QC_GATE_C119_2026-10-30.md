# R-01 Manuscript QC and publication release gate — C119
Date: 2026-10-30. Owner: R-01. Scope: scholarly manuscripts only; no VPS factory or live-site changes.

## Mandatory acceptance checklist
1. Manuscript identity: title, article type, version, full author contributions and affiliations individually confirmed; no invented qualifications.
2. Source provenance: every numerical claim maps to original source, page/table, denominator, unit, and retrieval evidence; discrepancies logged explicitly.
3. Data/methods: original data permission and version/hash, reproducible computations, assumptions, missingness, uncertainty and limitations; narrative review must not claim systematic methods.
4. Novelty: comparison against primary prior art, no first-ever claim without evidence.
5. Ethics/rights: conflicts, funding, data rights, plagiarism and image permissions reviewed; human-author approval documented before external submission.
6. Editorial: complete abstract, methods, results/synthesis, discussion, limitations, reference verification, journal fit, reporting checklist, and journal-specific formatting.
7. Independent scientific review: substantive reviewer findings closed or accepted with documented rationale; no automatic pass based on file count or green CI.
8. Publication: record exact journal, author-approved submission package and actual submission receipt; subsequent editorial decision, acceptance DOI and public publication URL recorded separately. Never label submitted/accepted/published before evidence.

## MR-2026-001 disposition from inspected C118 manuscript
- READY_FOR_REVIEW only. Critical source arithmetic discrepancies Car Table 5 74 vs 72 and Table 6 41 vs 40: BLOCKED on primary correction or explicit author-approved limitations.
- Amini F7 inconsistent numerical differences: BLOCKED; no invented corrected number.
- Cvejić respondent roster and Baroni supplementary source access: BLOCKED; modeled outcomes must not be described as observed behavior.
- The review's claim is evidence-provenance adjudication, not a validated causal field trial. No new DOI, submission or acceptance evidenced.
- Gate verdict: **NO SUBMISSION** until author approves exact manuscript, source uncertainties are transparently adjudicated, journal requirements and permissions are checked, and submission credentials are available through an authorized channel.

## Next atomic actions
A. Compare C118 bibliography and tables to original Car publication and seek authentic erratum; if absent preserve unresolved counts in final manuscript with caveat.
B. Create reviewer response matrix: issue, original source, correction, residual uncertainty, reviewer decision.
C. Prepare journal-specific cover letter and submission package for author review, then submit only after explicit approval and retain submission receipt.

Release states: DRAFT -> SOURCE_QC -> METHODS_QC -> INDEPENDENT_REVIEW -> AUTHOR_APPROVED -> SUBMITTED (receipt) -> ACCEPTED (editorial letter) -> PUBLISHED (public URL). These are never interchangeable.

# R-01 C127 — executed full-document QA and journal release verdict
Date: 2026-10-30. Owner R. No public submission or publication.

## Real file artifacts
- [Complete C127 source manuscript](../manuscripts/MR-2026-001/MR-2026-001_C127_SOURCE_DISPOSITION_AUTHOR_REVIEW_MANUSCRIPT_2026-10-30.md), 69,595 characters, 25 sequential references.
- [C127 source-to-claim matrix](../manuscripts/MR-2026-001/MR-2026-001_C127_SOURCE_CLAIM_MATRIX_2026-10-30.tsv), 14 populated unique claims.
- Complete C127 Word manuscript was created from the full 8,401-word C125 Word source, revised with source-specific §5.7, rendered to 16 pages and inspected at the new subsection. Private Library: `/Research/MR-2026-001/MR-2026-001_C127_source_disposition_author_review.docx`. SHA-256: `4e6e5e1b68c253a849874d49fe5601f55f6accc1e6a42c63478a2f34c192e2d1`.
- Private Library machine-readable audit: `/Research/MR-2026-001/MR-2026-001_C127_DOCX_QC.json`.

## Executed checks (scope stated precisely)
**Python on actual DOCX:** 8/8 structural checks passed: full sections, new §5.7, Car arithmetic markers, Amini F7 source discrepancy, fidelity caveat, 25 sequential references, no TODO placeholders, no false acceptance statement. 252 paragraphs, 8,664 words; 16 rendered pages. Visual review of inserted section on page 14 found no clipping or table overflow. These checks do **not** verify every reference or scientific claim.

**JavaScript on actual GitHub file contents:** 9/9 checks passed: complete sections, 25 references, 14 complete evidence rows, unique IDs, new primary-source Amini implementation-language row, no false publication claim, cross-assist source presence, MOJ1 nofollow candidate presence, dairy instrument presence. All checked files were fetched back from the branch.

**MOJ1 offline Python regression:** 8/8 synthetic tests passed for the standalone nofollow file-hash candidate (regular file, wrong digest, traversal, file symlink, directory symlink, root symlink, directory-as-file, uppercase digest). This does **not** prove full security or eliminate hostile root-ancestor TOCTOU races.

## New scientific editorial correction
The original Amini publisher text explicitly describes a farmer *attempting* to implement a DSS irrigation schedule with local date/time adjustments. C127 therefore codes this as a reported implementation attempt, **not objectively logged event-by-event adherence**. The review preserves the Car 74/72 and 41/40 inconsistencies and Amini F7 −1.3/−1.4/−0.1 discrepancy without inventing a corrected value.

## Fail-closed publication gate
Eight unresolved source rows: `C120-02, C120-03, C120-04, C120-06, C120-07, C120-08, C123-10, C124-12`. Source disagreements may remain only as transparently excluded claims after independent scientific review and human author approval. Authenticated author contributions, AI-use disclosure, journal fit/format, funding/competing interests, data and image permissions, and journal submission credentials/receipt remain absent.

**Verdict: READY_FOR_REVIEW (document); BLOCKED (submission); NOT SUBMITTED / NOT ACCEPTED / NOT PUBLISHED.**

No factory VPS/master-agent writes, service changes, deployment, payment or public publication.

# Research / CV / MOJ1 checkpoint — C73 — 2026-10-28

**Deliverable ID:** ZM-R01-C73-FACTORIAL-GATE-v1. **Status:** READY_FOR_REVIEW (code change + metadata-only regression tests); **NOT** a biologically validated RNA-seq pipeline or completed paper. Final approved scientific deliverables: **0**. Journal submissions: **0**.

## Actual new change since C72

- [Updated preflight](quality_gates/zm_r01_preflight.py) at Git blob SHA `bd116e6c18c751109e16d55dcb1558ea543e8794`; source commit [9fc46981](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/9fc46981dabd7b1ad38198af13fc614b28f01876).
- [New regression tests](quality_gates/test_zm_r01_factorial_design.py) at Git blob SHA `eda67272ab43aafedf1eb9371623aa1e2a2788c5`; commit [b5c673b2](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/b5c673b205386ccd1341a489c5440195a7dfa683).
- **Before:** the preflight accepted any layout with at least two conditions and at least two recorded replicates per condition. A 12+12 two-condition layout could pass even though the intended experiment is 2×2×2 with 24 libraries.
- **After:** exact condition strings `000` through `111`, each with precisely three recorded libraries, are mandatory. Two-condition 12+12, unbalanced 4+2 cells and missing leading-zero labels now fail closed. The existing unique library ID, (condition, replicate) pair, FASTQ file hashes and raw integer-count file checks remain in place.

## Reproducibility and evidence scope

1. Fetch the exact two GitHub files from the research branch and verify the blob SHAs above.
2. Run `python -m unittest discover -s research/quality_gates -p 'test_zm_r01_factorial_design.py' -v` from the repository root in Python 3.11. Four metadata-only cases are included (one balanced layout accepted, three invalid layouts rejected).
3. A matching isolated local Python helper check was actually executed during this cycle and passed for the same one-valid/three-invalid layouts. **The committed repository test suite was not executed in GitHub Actions or against real 24-library biological files in this cycle; do not claim a CI PASS.**
4. The gate checks recorded experimental layout, not whether labels are authentic, chambers are independent, reads were sequenced correctly, count-generation is valid, or DEG/FDR is scientifically supported.

## Unchanged scientific and publication gates

- **MR:** [C72 working manuscript](manuscripts/MR-2026-001/MR-2026-001_C72_MISSINGNESS_AWARE_SOURCE_PROVENANCE_MANUSCRIPT_2026-10-28.md) remains READY_FOR_REVIEW / MAJOR REVISION. Original Car Table 5/6 contradictions, Amini F7, exact Cvejić survey denominator, Lorite/Baroni/Elia methods and independent G/D/R/A event evidence unresolved; author contribution and approval pending. No new MR scientific result claimed in C73.
- **AE:** [official WDI archive provenance gate](manuscripts/AE-2026-001/AE-2026-001_WDI_OFFICIAL_ARCHIVES_PROVENANCE_GATE_2026-10-28.md) remains BLOCKED for historical ZIP bytes, SHA256, historical ILOSTAT provenance and executed countryatlas benchmark. C13/C14 are previous outputs, not newly validated. Same-source WDI/ILOSTAT limitation persists.
- **ZM:** exact IWGSC RefSeq v2.0 FASTA/GTF/real checksums, true 48 FASTQ MD5, multimapping/strandedness and independence evidence, 24-column genuine integer count matrix, DESeq2 and FDR are all unresolved. FPKM and 1167 exploratory hypotheses are **not** DEG/FDR. No 149.54GB download, VPS or expenditure.
- **CV:** [Persian](profile/cv/MOJ_ROOZEGAR_CV_FA_2026-10-28_v1_REVIEW_ONLY.md) and [English](profile/cv/MOJ_ROOZEGAR_CV_EN_2026-10-28_v1_REVIEW_ONLY.md) remain unapproved READY_FOR_REVIEW; unverified education/roles/publications must not be promoted as facts. No new public CV version published.
- **MOJ1:** prior private audit-input artifact `12406875421` already archived and recorded in [issue #853](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/853); not a new action or outstanding archive failure. Existing auditor correspondence dated 2026-10-27 (ShellBoxes: up to 30% MOJ1 conditional on approval; Codeum: preliminary $800 and liquid-currency payment) is not confirmed funding or an independent audit. Sponsor, audit, legal gate and mainnet release remain BLOCKED; no financial action.
- **Web:** staging only; no live website edit, publication, PR #1054 merge, social-account interaction or institutional submission.

**Next highest-value step:** obtain original archive/biological source evidence; only then run real data validation and advance manuscript stages. Do not re-count this metadata gate or prior C72 as fresh work next cycle.

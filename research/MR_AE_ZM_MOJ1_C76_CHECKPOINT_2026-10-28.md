# R-01 / C76 — recoverable scientific and provenance checkpoint
Date: 2026-10-28, Asia/Tehran. Run ID: R-01-20261028T1517+0330-C76.
WIP: (1) MR author-review evidence pack; (2) ZM RNA-seq preflight hardening. No new research project started.

## 1. MR-C76 — READY_FOR_REVIEW (NOT DELIVERED as a final journal article)
- Before: C75 manuscript, Git blob `3def23d8db1dc13e6399d462cdffbcd93151f873`, already flagged Table 5 count and category crosswalk discrepancies.
- After: [C76 complete manuscript](manuscripts/MR-2026-001/MR-2026-001_C76_CAR_INFLUENCE_CLAIM_DENOMINATOR_AUDIT_MANUSCRIPT_2026-10-28.md), blob `8eb273835fa72dbf0956a4c77d2f9ed74cc8f4d9`, [commit cf94a73](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/cf94a73b1908bf127cd5f790b541e36402f3393a).
- New **five source-specific editorial adjudications** from Car et al. 2012 author-uploaded printed text: (1) group 2+3 stated 46%, count-derived 10/72=13.89%; (2) group 1+2+3 stated 73%, count-derived 36/72=50%; (3) adding group 5 stated 80%, count-derived 51/72=70.83%; (4) Nov rainfall reporting 51/54=94.44%; (5) Dec rainfall reporting 54/72=75%. The latter two are rainfall response, not verified implementation. These are five corrections within **one** substantive author-review manuscript, not five papers or independent validated outcomes.
- Source: [author-uploaded article text](https://www.researchgate.net/publication/257018309_Using_a_mobile_phone_Short_Messaging_Service_SMS_for_irrigation_scheduling_in_Australia_-_Farmers%27_participation_and_utility_evaluation), printed pp. 138–141, and [UNE abstract](https://rune.une.edu.au/entities/publication/68f9d1ef-6e62-415a-b831-0beb96df9853). Publisher-original table images, erratum and person-level category crosswalk still unavailable. Do not infer behavioral prevalence.
- Reproduce: inspect C76 section 7.3; evaluate the five rational expressions above. GitHub content was independently read back and checked for all five values and section 7.3. This is a content integrity check, **not** independent scientific peer review.

## 2. ZM preflight — READY_FOR_REVIEW code; tests NOT VERIFIED
- Before: [preflight source](quality_gates/zm_r01_preflight.py) Git blob `deae2f275b1fa05acf7888f7fbb39be87f653b7c` checked file hashes and contig-name presence, but not FASTA sequence alphabet, empty contigs, annotation interval validity, global reuse of replicate IDs or strict versioned assembly accessions.
- After: [preflight source](quality_gates/zm_r01_preflight.py), Git blob `d495d498b9840f7c46dd8e987ebf62fc34013b16`, [commit a88e751](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/a88e7513b15aaece6479b8f2ac4b43a32bd6a09d). Distinct fail-closed controls: (1) FASTA IUPAC/empty/duplicate/header validation and contig lengths, (2) GTF/GFF interval/strand/frame/attributes and FASTA bounds, (3) global biological replicate ID uniqueness with repeated-measures design escalation, (4) strict 2x2x2 condition and library-ID safety checks, (5) numeric-versioned GCF/GCA assembly accession syntax.
- [11 reproducible regression tests](quality_gates/test_zm_r01_reference_preflight.py), blob `13a5d0e21047d33904f581998d1bd440aa6c4384`, [commit 2cc52d1](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/2cc52d1c318fca50746cbf1fb9bee64a97f5a2ff).
- Reproduce from checked-out branch: `python -m unittest discover -s research/quality_gates -p 'test_zm_r01_reference_preflight.py' -v`. **Tests were committed but not executed/green-verified in this run.** Synthetic parser fixtures are not biological samples and produce no DEG/FDR. CI runs are still pending; no release/deployment claimed.
- No exact RefSeq v2.0 reference FASTA/GTF or checksums, no real FASTQ MD5, no real integer counts, no validated replicate independence, no DESeq2, no 149.54GB download or VPS work.

## Other carryover (no stage change)
- AE: C13/C14 are old. Official WDI archive locators known, but 2024/2025/2026 archive bytes/SHA and historical ILOSTAT, countryatlas execution missing. MAJOR REVISION.
- CV FA/EN v2: READY_FOR_REVIEW; no new credential validation; no live site publish.
- MOJ1: [security issue #853](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/853) remains MAINNET NO-GO, independent audit/sponsor/legal gates BLOCKED. Previously archived private artifact 12406875421 is **not** a new success.
- Site staging: no new deployed page or visual validation. A GitHub workflow called "Publish evidence-based Mojtaba scholarly CV" completed verify-only with publish job SKIPPED (run 40683008950); this is not a live site change. No Instagram/Facebook, no PR #1054 merge.
- No journal submission, payments, token transfers, contract, public CV release, or permission-sensitive actions.

## Outcome accounting and exact next atomic step
Two recoverable work products: **MR-C76 manuscript READY_FOR_REVIEW** and **ZM code patch READY_FOR_REVIEW, regression execution pending**. Zero final human-approved papers, zero article stage transitions. Five Car quantitative editorial adjudications and five distinct ZM guard changes were implemented, but these do not equal ten final deliverables or ten validated research outcomes.
**Next first action:** execute and capture the exact ZM regression command on the checked-out branch, correct any failures, then obtain publisher-authenticated Car Tables 4–6/erratum; do not change the live site or deploy.

# R-01 / C84 — Conservative source-adjudication manuscript and author pack
**run_id:** R-01-20261028T2315+0330-C84. **Date:** 2026-10-28. **Branch:** `research/mr-2026-001-novelty-audit`. **Carryover:** [issue #1514](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514) and [C83](MR_AE_ZM_MOJ1_C83_CHECKPOINT_2026-10-28.md). **WIP=1:** MR manuscript + its inseparable author-review pack. **Status:** READY_FOR_REVIEW; journal-ready final DELIVERED=0, submission=0, stage transfer=0.

## Four fresh substantive scientific corrections (not commits/tests/report counted)
1. **Amini F7 rounding inference repaired:** displayed 4.6−6.0=−1.4 kg/m³, but rounded inputs may represent a true difference approximately (−1.50,−1.30) kg/m³. Example 4.649 (prints 4.6) minus 5.951 (prints 6.0) = −1.302, which prints −1.3. Therefore Results' −1.3 is *not proven contradictory* from the displayed rounded table. Conclusion's −0.1 is incompatible with this rounding alone and still needs primary data/author correction. [Publisher article](https://www.nature.com/articles/s41598-025-26567-z).
2. **Car main-text numeric quarantine:** disputed Table 5/6 and 46/73/80 perceived-influence values no longer treated as primary quantitative evidence. Source-internal calculations remain in §§7.2–7.4 for adjudication; no fabricated correction. [UNE university record](https://researchers.une.edu.au/en/publications/using-a-mobile-phone-short-messaging-service-sms-for-irrigation-s-5/); [author-uploaded typeset text](https://www.researchgate.net/publication/257018309_Using_a_mobile_phone_Short_Messaging_Service_SMS_for_irrigation_scheduling_in_Australia_-_Farmers%27_participation_and_utility_evaluation).
3. **Cvejić item-response overreach removed:** percentages compatible with N=35 do not authenticate per-item response counts. Removed 29/35 and 25/35 as reconstructed observed item data from main case narrative; retained source's own 6% (two farmers) and original 46-versus-35 uncertainty. [Publisher article](https://doi.org/10.3390/agronomy10091238).
4. **False independence of Car crosswalk repaired:** arithmetic and semantic mappings are both from the *same* author-uploaded paper; two checks are not two independent sources. Manuscript and author pack now explicitly state within-source, non-independent corroboration.

## Deliverable and before/after evidence
- [Full MR C76 v10 working manuscript](manuscripts/MR-2026-001/MR-2026-001_C76_CAR_INFLUENCE_CLAIM_DENOMINATOR_AUDIT_MANUSCRIPT_2026-10-28.md). Before Git blob `8cc1cf0c9e4a2eb231a66b981d89b2404d238aa4`; after `70461b0860e8e684190f2b4bf0c1c48a5d357e61`. Material [commit 74f4239](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/74f42394556ea88feb168d8c7cc179531b1e9241), wording QA [9eacb7b](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/9eacb7be3700a460a1c91807e14dbd514de418d8).
- [Source-to-claim author decision pack](manuscripts/MR-2026-001/MR-2026-001_C78_CORRECTED_SOURCE_TO_CLAIM_AUTHOR_DECISION_PACK_2026-10-28.md). Before `5005f069ef6e29794b4c0e8f224cd64aaed93640`; after `c4d0a4c8a0c7c6bef88b841cb7c9c46704ff6f7c`. [Commit 41aab5f](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/41aab5f7b0b8da694d71d20cb832a219daf86cf6), wording QA [008a866](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/008a86622ce58ba76cac5a20a778542f6115623c).
- **Reproducible checks after independent re-fetch: 10/10 editorial guards PASS** (both v10 refs; arithmetic witness display and effect; −0.1 excluded; Car primary quarantine; Cvejić no inferred item counts; non-independent crosswalk; no stale v9 references; journal gate). This is **not independent scientific peer review or field validation**.

## Open gates and stage
MR: Car original Table 5/6 and correction, Amini unrounded F7 and −0.1, Cvejić item N/46, full Lorite/Baroni/Elia, G/D/R/A empirical validation, human author substantive participation, byline/affiliation, COI/funding/AI, rights/journal/APC and exact-version approval **BLOCKED**. AE: WDI archives/SHA, ILOSTAT historical and current, same-source sensitivity and countryatlas **NOT_DONE**. ZM: exact v2.0 licensed reference, real FASTQ hashes and integer counts, actual DESeq2 **BLOCKED**; no FPKM→DEG claim or 149.54GB download. CV FA/EN: no new verified credentials, **NOT_DONE**. Web: no staging or live changes. MOJ1: prior private audit artifact is not a new action; independent signed audit, sponsor and legal approval remain BLOCKED. No payments, submissions, contracts, token deploy, PR #1054 merge or prohibited social interaction.

## X/25 — MR/AE
| # | Action | Status |
|---:|---|---|
| 1 | Amini F7: rounding-compatible −1.3 separated from unexplained −0.1 | موفق؛ READY_FOR_REVIEW |
| 2 | Car disputed 46/73/80 excluded from main numerical synthesis | موفق؛ READY_FOR_REVIEW |
| 3 | Cvejić inferred item counts removed without response ledger | موفق؛ READY_FOR_REVIEW |
| 4 | Car semantic/arithmetic checks classified as within-source, non-independent | موفق؛ READY_FOR_REVIEW |
| 5 | Authenticate Car publisher Table 5/6 | ناقص؛ NOT_DONE/BLOCKED |
| 6 | Resolve Car Table 5 74/72 | ناقص؛ NOT_DONE/BLOCKED |
| 7 | Resolve Car Table 6 40/41 | ناقص؛ NOT_DONE/BLOCKED |
| 8 | Resolve Car Group 4/5 reversal | ناقص؛ NOT_DONE/BLOCKED |
| 9 | Resolve Car 68%/50% discrepancy | ناقص؛ NOT_DONE/BLOCKED |
| 10 | Obtain Amini unrounded F7 data/erratum | ناقص؛ NOT_DONE/BLOCKED |
| 11 | Verify Cvejić item-specific survey N | ناقص؛ NOT_DONE/BLOCKED |
| 12 | Clarify Cvejić 46 email users | ناقص؛ NOT_DONE/BLOCKED |
| 13 | Verify full Lorite methods | ناقص؛ NOT_DONE/BLOCKED |
| 14 | Verify full Baroni methods | ناقص؛ NOT_DONE/BLOCKED |
| 15 | Verify full Elia methods | ناقص؛ NOT_DONE/BLOCKED |
| 16 | Empirically validate G/D/R/A | ناقص؛ NOT_DONE/BLOCKED |
| 17 | MR human author source and substantive review | ناقص؛ NOT_DONE/BLOCKED |
| 18 | MR exact-version publication authorization | ناقص؛ NOT_DONE/BLOCKED |
| 19 | AE recover C13/C14 full evidence | ناقص؛ NOT_DONE/BLOCKED |
| 20 | WDI 2024 original archive + SHA | ناقص؛ NOT_DONE/BLOCKED |
| 21 | WDI 2025 original archive + SHA | ناقص؛ NOT_DONE/BLOCKED |
| 22 | WDI 2026 original archive + SHA | ناقص؛ NOT_DONE/BLOCKED |
| 23 | ILOSTAT historical/current provenance | ناقص؛ NOT_DONE/BLOCKED |
| 24 | countryatlas direct benchmark and shared-source sensitivity | ناقص؛ NOT_DONE/BLOCKED |
| 25 | AE manuscript author-ready final | ناقص؛ NOT_DONE/BLOCKED |

## Y/25 — ZM/CV/web/MOJ1
| # | Action | Status |
|---:|---|---|
| 1 | ZM exact RefSeq v2.0 FASTA | ناقص؛ NOT_DONE/BLOCKED |
| 2 | ZM matching GTF/GFF | ناقص؛ NOT_DONE/BLOCKED |
| 3 | ZM reference checksum | ناقص؛ NOT_DONE/BLOCKED |
| 4 | ZM reference access rights | ناقص؛ NOT_DONE/BLOCKED |
| 5 | ZM 24 biological samples provenance | ناقص؛ NOT_DONE/BLOCKED |
| 6 | ZM 48 FASTQ true MD5 | ناقص؛ NOT_DONE/BLOCKED |
| 7 | ZM strandedness | ناقص؛ NOT_DONE/BLOCKED |
| 8 | ZM multimapping policy | ناقص؛ NOT_DONE/BLOCKED |
| 9 | ZM integer count matrix | ناقص؛ NOT_DONE/BLOCKED |
| 10 | ZM real DESeq2 | ناقص؛ NOT_DONE/BLOCKED |
| 11 | ZM valid DEG/FDR | ناقص؛ NOT_DONE/BLOCKED |
| 12 | ZM final manuscript and author approval | ناقص؛ NOT_DONE/BLOCKED |
| 13 | FA CV independent evidence | ناقص؛ NOT_DONE/BLOCKED |
| 14 | EN CV independent evidence | ناقص؛ NOT_DONE/BLOCKED |
| 15 | Education proof | ناقص؛ NOT_DONE/BLOCKED |
| 16 | Professional role proof | ناقص؛ NOT_DONE/BLOCKED |
| 17 | Publication/DOI proof | ناقص؛ NOT_DONE/BLOCKED |
| 18 | Future topics originality screen | ناقص؛ NOT_DONE/BLOCKED |
| 19 | Future topics data/licensing screen | ناقص؛ NOT_DONE/BLOCKED |
| 20 | Mojtaba staging artifact | ناقص؛ NOT_DONE/BLOCKED |
| 21 | MOJ1 contract/security new evidence | ناقص؛ NOT_DONE/BLOCKED |
| 22 | MOJ1 sponsor confirmed | ناقص؛ NOT_DONE/BLOCKED |
| 23 | MOJ1 independent audit | ناقص؛ NOT_DONE/BLOCKED |
| 24 | MOJ1 archived private audit artifact 12406875421 (previously done) | قبلاً تکمیل‌شده؛ خارج از شمارش |
| 25 | MOJ1 legal launch authorization | ناقص؛ NOT_DONE/BLOCKED |

**New count:** X=4 successful scientific corrections, 21 incomplete; Y=0 new, 24 incomplete, 1 prior completion excluded. **4/50 new; 45 incomplete; 1 prior; 0 recorded failures.** Minimum five substantive actions missed by one, carried forward. **Final approved papers=0; stage transfers=0.**

**First exact next action:** obtain/authenticate publisher-original Car Table 5/6 or author erratum, and compare with the source-audit appendix. If unavailable, keep all contested counts quarantined and independently source-check Amini F7 unrounded farm-level table or correction. Do not start new research topics ahead of the MR evidence gate.

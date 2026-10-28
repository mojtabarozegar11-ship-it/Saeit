# R-01 / C80 — positive evidence extraction and internal source contradiction, 2026-10-28

**run_id:** R-01-20261028T1912+0330-C80  
**Carryover:** [Shared issue #1514](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514), [C79 checkpoint](MR_AE_ZM_MOJ1_C79_CHECKPOINT_2026-10-28.md).  
**WIP:** (1) MR author-review narrative manuscript, (2) ZM exact-reference/data-provenance gate. No new project opened.

## Material output (READY_FOR_REVIEW, not author-approved)

Updated the **existing** [MR working manuscript C76 v5](manuscripts/MR-2026-001/MR-2026-001_C76_CAR_INFLUENCE_CLAIM_DENOMINATOR_AUDIT_MANUSCRIPT_2026-10-28.md), Git blob `363114f8a38e1aa9f7933c1d2e504070fca1a7fc`, commit [9cc43f6](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/9cc43f6f0be4bfc73332f1cf7580c59c20a5a25d). Synchronized the [eight-case author decision pack](manuscripts/MR-2026-001/MR-2026-001_C78_CORRECTED_SOURCE_TO_CLAIM_AUTHOR_DECISION_PACK_2026-10-28.md), Git blob `615341c82e3b772f6b506640767b5146201b1da4`, commit [ab74c71](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/ab74c719635db4f4bf87c1e52152fb51df74d4).

Three distinct substantive evidence corrections, not five deliverables:

1. **Car (2012), positive decision-consideration measure:** Original author-uploaded printed text §3.4 reports **53 of 72 (74% rounded) irrigators said they actively considered the DSS when scheduling**. Added it as an explicitly *self-reported decision-input* measure, not advice-event adherence or observed water saving. Source [author-uploaded printed article, p. 139](https://www.researchgate.net/publication/257018309_Using_a_mobile_phone_Short_Messaging_Service_SMS_for_irrigation_scheduling_in_Australia_-_Farmers%27_participation_and_utility_evaluation). Distinct from [UNE institutional record](https://researchers.une.edu.au/en/publications/using-a-mobile-phone-short-messaging-service-sms-for-irrigation-s-5/)'s 45/72 full-season data-return outcome; overlap not established.
2. **Car (2012), prospective intention separated from actual retention:** Printed discussion §4.2 says **69% of the original 72 wished to use the system next season**, and **83% among full-season users**. Added only as *stated intent*, without invented person counts or observed next-season behavior.
3. **Cvejić et al. (2020), internal exposure-frame contradiction:** The [publisher article](https://www.mdpi.com/2073-4395/10/9/1238) describes **35 participating farms** but Results literally state **46 farmers use e-mail irrigation advice**. The earlier working draft treated 46 as an independent exposure count without evidence. It now flags an unresolved source inconsistency and excludes the 46 count pending author/publisher clarification. 83%, 71%, 6% (two farmers) remain compatible with a *candidate* N=35, not independently verified per-item N.

## Before/after and verification

**Before:** MR draft had no independently labeled 53/72 positive consideration extraction, no explicit future-use intention distinction, and asserted 46 e-mail advice recipients as a separate exposure frame. Its header also overstated the Table 6 arithmetic match as a resolved attribution in one historical provenance sentence.  
**After:** Two source-linked, source-bound Car outcomes added; Cvejić 46-versus-35 quarantined; manuscript provenance line corrected to the C79 unresolved numbered-to-unnumbered crosswalk. Eight-case claim/evidence table and author decisions aligned. No source aggregate changed or fabricated.

**Reproduce arithmetic:** `53/72*100 = 73.611111...`; `45/72*100 = 62.5`; `29/35*100 = 82.857142...`; `25/35*100 = 71.428571...`; `2/35*100 = 5.714285...`. These reproduce *reported figures*, not raw data or item-level denominators. Both GitHub files were independently fetched after commits and exact blob SHA matched. This is a manuscript-level editorial evidence correction, not human peer review, real-world field testing, an approved article, or publication.

## Gates and carryover

- **MR:** Publisher-authenticated Car Tables 5/6, group crosswalk, 74/72 and 40/41, Amini F7, Cvejić item-level N and 46-vs-35 clarification, Lorite/Baroni/Elia full methods, prospective G/D/R/A validation or explicitly conceptual framing, human author's substantive participation and exact-version approval. **Major Revision; no submission.**
- **AE:** Historical WDI 2024/2025/2026 ZIP bytes and SHA, independently archived ILOSTAT vintages, `countryatlas::compare_vintages` real benchmark still missing. C13/C14 not counted as fresh work; branch-local file retrieval not established this run. **Major Revision.**
- **ZM:** IWGSC v2.0 exact licensed FASTA/GTF/SHA, 48 real FASTQ MD5, biological independence, raw integer count matrix, DESeq2/FDR missing. No large download or VPS access. **Data Rebuild.**
- **CV/staging:** prior FA/EN v2 still review-only; no new credentials verified and no staging/live changes.
- **MOJ1:** prior audit artifact 12406875421 already archived, not new; independent audit, funded sponsor and legal authorization remain blocked. No payments, correspondence, deployment or sale.

**New substantive scientific actions: 3**, not the five-action target; two derivative file edits are not counted as extra independent actions. **New author-review output READY_FOR_REVIEW: 1 coherent updated package; final approved paper DELIVERED: 0; article stage transfers: 0; submissions: 0.**

**First exact next action:** obtain the authentic Car publisher table images or correction and compare numbered groups to unnumbered Table 6; if unavailable, continue source-grounded MR manuscript without extracting disputed 46/73/80 prevalence. Next, obtain Cvejić's original item-level questionnaire response counts and reconcile 46-vs-35, without inventing an extra sample.

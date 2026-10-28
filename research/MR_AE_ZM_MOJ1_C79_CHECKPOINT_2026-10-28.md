# R-01 / C79 — Car source-attribution correction, not a new scientific finding

**run_id:** R-01-20261028T1817+0330-C79  
**Date:** 2026-10-28 Asia/Tehran  
**Carryover:** [Shared R-01 issue #1514](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514); [C78 checkpoint](MR_AE_ZM_MOJ1_C78_CHECKPOINT_2026-10-28.md).  
**WIP:** (1) MR author-review paper; (2) ZM reference identity/data gate. No new research topic, journal submission, website release, or mainnet action.

## New substantive implementation: 2 distinct edits, one author-review deliverable

1. **MR source inference corrected:** [C76 working manuscript v4](manuscripts/MR-2026-001/MR-2026-001_C76_CAR_INFLUENCE_CLAIM_DENOMINATOR_AUDIT_MANUSCRIPT_2026-10-28.md) Git blob `c3c130a3f83f92f8514b8706f3e14a7fa2ceb5c4`, [commit](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/28fdde777106f702ba74b072f73d1246adbf9d08). The previous C76 v2 incorrectly assumed Table 5 was the denominator of Car's 46/73/80 influence claims; C78 overcorrected by claiming the Table 6 arithmetic *resolved* attribution. The author-uploaded printed text refers to numbered Groups 2/3/1/5, whereas Table 6 labels Small/Large/Significant/None/Marginal are **unnumbered**. The 19/41=46.34%, 30/41=73.17%, 33/41=80.49% numerical match is a **candidate**, not an authenticated category mapping. Excluded the three rates from any quantitative extraction until the original source crosswalk is verified. Preserved 40-vs-41 and 74-vs-72 disagreements.
2. **Author decision pack aligned:** [C78 author-review decision pack](manuscripts/MR-2026-001/MR-2026-001_C78_CORRECTED_SOURCE_TO_CLAIM_AUTHOR_DECISION_PACK_2026-10-28.md) Git blob `9e3d084025130c258fb6d007bf8dd8bd40cc1ebe`, [commit](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/edae6590f36e81b4b53ee2020b72775da139a31d). Corrected the claim/evidence table, eight author decisions, author-ready replacement paragraph and reproduction note to prohibit treating the numerical coincidence as a verified survey-category crosswalk.

**Source checks:** [Author-uploaded printed article, pp. 139–141](https://www.researchgate.net/publication/257018309_Using_a_mobile_phone_Short_Messaging_Service_SMS_for_irrigation_scheduling_in_Australia_-_Farmers%27_participation_and_utility_evaluation); [University of New England institutional record](https://rune.une.edu.au/entities/publication/68f9d1ef-6e62-415a-b831-0beb96df9853). The institutional abstract independently supports 45+13+14=72 at the *engagement-duration* level, not the disputed behavior-group coding. Publisher version of record/erratum **not** authenticated. No original data acquired or invented.

**Reproducible checks:** Table 6 `[11,10,9,8,3].reduce(sum)=41`; Table 5 `[26,7,3,6,15,17].reduce(sum)=74`; Table 6 candidate arithmetic `100*[19,30,33]/41 = [46.34146,73.17073,80.48780]`. Both modified files were **re-fetched from the requested GitHub branch** and blob SHAs matched; both contain an explicit unresolved-crosswalk and no-quantitative-extraction warning. No human source authentication, peer review or author approval is implied.

**Deliverable status:** manuscript and author packet **READY_FOR_REVIEW** (scientific error corrected; still incomplete for publication); final author-approved article **NOT_DONE**; journal submission **NOT_DONE**; paper stage transfer **0**. New implementation actions **2**, not five; searches, readbacks, tests and checkpoint writing **not counted** as implementation actions. Remaining 48 of the 50 target slots are not evidenced as completed in this run.

## Carryover gates

- **MR:** publisher-original Car Tables 5/6, numbered-group crosswalk and 40/41 and 74/72 conflicts; Amini F7 source contradictions; Cvejić item-specific survey N; Lorite/Baroni/Elia full methods; independent G/D/R/A validation or explicitly conceptual treatment; intended human author's substantive review and exact-version approval.
- **AE:** C13/C14 remain historical prior work; no new authenticated 2024/2025/2026 WDI archive bytes/SHA, historical ILOSTAT or direct countryatlas benchmark. No novelty claim.
- **ZM:** exact IWGSC v2.0 licensed FASTA/GTF/checksums and 48 FASTQ MD5, strandedness, multimapping, integer raw counts, independent replicates and DESeq2 remain blocked. C78's 22-test CI success is **not verified in this run**; prior 19-test success is historical, not new. No 149.54GB download, VPS or expenditure.
- **CV/staging:** FA/EN v2 review-only; no new verified academic credential or staging change. Live site unchanged.
- **MOJ1:** prior audit artifact 12406875421 remains completed **previously**, not counted anew. Independent audit, committed sponsorship, legal authorization and mainnet remain **BLOCKED**; no external action or private correspondence disclosed here.

**First exact next action:** obtain an authenticated publisher/author source clarifying whether the printed Car influence paragraph's numbered groups refer to Table 5 or to an independent Table 6 recoding. If unavailable, keep the three rates excluded and move to direct Cvejić item-level denominator/method verification without inventing observations. Continue the ZM exact-assembly provenance gate as the second WIP.

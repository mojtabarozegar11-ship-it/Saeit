# R-01 / C89 checkpoint — 2026-10-29

Run ID: R-01-C89-20261029T0412+0330-R11. Branch: `research/mr-2026-001-novelty-audit`. Shared issue: https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514. WIP: 1 MR manuscript + 1 source-authentication blocker.

## Usable, versioned files — READY_FOR_REVIEW (not author-approved or submitted)
- [C89 full author-review manuscript](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/MR-2026-001/MR-2026-001_C89_CAR_RAINFALL_AND_GROUP1_AUTHOR_REVIEW_MANUSCRIPT_2026-10-29.md), Git blob `33c5a7953511b28e82bce64700596cc712d5ff6f`, commit `9bedc9c1f0547823a04a0cbafd39c3db8c4a07fc`. Previous C88 blob `771ebf8c09ba12d22f30700c7ad0c51a54c4fb9d` preserved.
- [C89 source-to-claim ledger](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/MR-2026-001/MR-2026-001_C89_CLAIM_TO_EVIDENCE_LEDGER_2026-10-29.tsv), Git blob `9371d00562f809ae0978fab018faf5e4a82e6ef4`, commit `2998580b8cb5771fafa40cbda1296df3d1326116`. Eight original cases retained, two distinct Car subclaims appended; 10 data rows, 11 columns.

## Two substantive, source-anchored scientific corrections
1. Car 2012 original-author-uploaded printed article Table 4 p.138: dated rain-input SMS counts **51/54=94.44%** (7–8 Nov 2008) and **54/72=75.00%** (12–14 Dec 2008), rather than one fixed survey denominator. The paper describes 75–95% rainfall reporting; these are **not irrigation implementation events**. Rain exposure varies by farm.
2. Car §3.4 p.139 and §4.2 p.141: Group 1 **within 10% suggested run time over the season**, not an independently validated event-level adherence tolerance. Table 5 printed count 26 is quarantined because 26+7+3+6+15+17=74 vs printed 72; Group 4/5 labels reversed. No invented corrected group count.

Primary source inspected: https://www.researchgate.net/publication/257018309_Using_a_mobile_phone_Short_Messaging_Service_SMS_for_irrigation_scheduling_in_Australia_-_Farmers%27_participation_and_utility_evaluation (author-uploaded article, **not publisher-certified version of record**). Source tables checked against web text, not original Elsevier page images.

## Read-back and release gates
Both newly written files fetched again from exact branch; UTF-8 text matched byte-for-byte; ledger 10 data rows and all 11 columns validated. This is document integrity QA, not peer review. **Fresh independent scientific corrections: 2** (no test/commit/report counted as a separate action); target 5 not reached. **Final human-approved manuscripts: 0; submissions: 0; phase transfers: 0.** MR/AE MAJOR REVISION; ZM DATA REBUILD; CV review-only; staging unchanged; MOJ1 blocked. No site, VPS, social, payment or token changes.

**BLOCKED:** Elsevier publisher-certified Car Tables 5/6 and correction, Amini F7 unrounded data, Cvejić per-item denominator, full Lorite/Baroni/Elia methods, G/D/R/A field validation and human-author scholarly decisions. Do not call source-authentication complete. No journal/author communications without separate authorization.

**First exact next action:** obtain publisher-authenticated Car Table 5/6 image or erratum and compare every row/label against the author-uploaded version; if still inaccessible, inspect Lorite 2012 complete methods and separately update its source-to-claim record without inferring farmer-event compliance.

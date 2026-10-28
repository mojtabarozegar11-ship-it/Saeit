# R-01 / C85 — 29 October 2026 — real manuscript correction + bilingual CV staging deliverables
**run_id:** R-01-C85-20261029; **branch:** `research/mr-2026-001-novelty-audit`; **WIP:** MR source-to-claim reviewer pack + bilingual CV (2). **No journal submission, public-site deployment, payment or token action.**

## Five new substantive outputs (not five commits, reports or QA checks)
1. **MR scientific correction:** UNE institutional abstract's author-reported **80% usefulness** cannot be inferred from the two accompanying counts: 45 full-season reporters plus six of 13 partial reporters who regretted stopping gives 51/72=**70.83%**, not 80%. Counting all 13 partial reporters would give 58/72=**80.56%**, but the source does not establish that all 13 rated the service useful. This does **not** prove the authors wrong; the item-level numerator remains unknown. Updated the complete MR manuscript **C76 v11** and linked author decision pack, preserving the discrepancy as an open gate. [UNE primary institutional record](https://researchers.une.edu.au/en/publications/using-a-mobile-phone-short-messaging-service-sms-for-irrigation-s-5/).
2. **English CV v3:** repaired two broken AE/ZM research links, replaced obsolete MR-C74 reference with C76 v11, corrected literal escaped line breaks, and distinguished owner-reported Vancouver/current Moj Play Win LLC and remote Zomorod management claims from independently verified credentials. Review-only, no public release.
3. **Persian CV v3:** same substantive evidence-link and role/qualification corrections in independently readable Persian; review-only.
4. **English HTML staging preview:** responsive, self-contained, no external script, noindex/nofollow; renders three current projects and evidence links, with owner-report and non-publication notices. Code candidate only, **not deployed to a staging server**.
5. **Persian HTML staging preview:** separate RTL, self-contained, responsive, noindex/nofollow; same science and credential gates, not deployed.

**Important counting rule:** MR author pack edit is part of action 1, not a sixth action; re-fetch, link QA and Git commits are verification, not extra implementation. CV and HTML are separate user-consumable formats, with two language-specific artifacts. All five are **READY_FOR_REVIEW**, none is a published/externally approved result.

## Recoverable outputs and read-back SHA (Git blob SHA-1, not file SHA-256)
| Output | Exact branch path | Git blob SHA-1 | Status |
|---|---|---|---|
| MR C76 v11 | [open](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/MR-2026-001/MR-2026-001_C76_CAR_INFLUENCE_CLAIM_DENOMINATOR_AUDIT_MANUSCRIPT_2026-10-28.md) | `643a4cd20b524fa804b7c24a5a5c531dbf0d9ef9` | READY_FOR_REVIEW |
| MR C78 updated author pack | [open](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/MR-2026-001/MR-2026-001_C78_CORRECTED_SOURCE_TO_CLAIM_AUTHOR_DECISION_PACK_2026-10-28.md) | `42c370a922d58935d51ee12e6252fa321e206978` | READY_FOR_REVIEW |
| CV EN v3 | [open](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/profile/cv/MOJ_ROOZEGAR_CV_EN_2026-10-29_v3_REVIEW_ONLY.md) | `56f8223ee52759ac748be30cb20f9168dce39f6a` | READY_FOR_REVIEW |
| CV FA v3 | [open](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/profile/cv/MOJ_ROOZEGAR_CV_FA_2026-10-29_v3_REVIEW_ONLY.md) | `c8c78de500768a8fad36276f89e3e17be36a2dcd` | READY_FOR_REVIEW |
| EN staging HTML | [open](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/profile/staging/mojtaba_roozegar_cv_en_v3_2026-10-29.html) | `2cdb0786394a3f92994312c48793018dfb36a22e` | READY_FOR_REVIEW |
| FA staging HTML | [open](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/profile/staging/mojtaba_roozegar_cv_fa_v3_2026-10-29.html) | `2a7f9fa95e2050350359e866a27d9010f745f7d4` | READY_FOR_REVIEW |

**Before/after:** MR manuscript blob `7dbbf8f463a95a82c5aaa1f4bca566c3fc9bafe4` → `643a4cd20b524fa804b7c24a5a5c531dbf0d9ef9`; MR pack `c4d0a4c8a0c7c6bef88b841cb7c9c46704ff6f7c` → `42c370a922d58935d51ee12e6252fa321e206978`. English CV v2 `4b25766a197128ae1eaae8cd2cbd0a17f8962b46` → new v3 `56f8223ee52759ac748be30cb20f9168dce39f6a`; Persian CV v2 `ce63e0f3012c3321374092f5d0edb9768123b18c` → new v3 `c8c78de500768a8fad36276f89e3e17be36a2dcd`.

**Reproducible source arithmetic:** `(45+6)/72*100 = 70.833333...`; `(45+13)/72*100 = 80.555555...`. This identifies an unverified usefulness numerator; it does not authenticate the publisher's raw questionnaire. **Read-back QA:** all six linked files were fetched again from the named branch; six of six passed version/status/no-sensitive-credentials/no-false-publication and expected-source checks. The existing AE and ZM targets of the repaired CV links were fetched and exist. HTML has noindex meta and contains no external scripts. These are editorial/integrity checks, not independent peer review, accessibility certification or deployment tests.

## X/25 — MR and AE
| # | Work item | New-run result |
|---:|---|---|
| 1 | UNE abstract usefulness numerator and MR C76 v11 | موفق؛ READY_FOR_REVIEW |
| 2 | Car publisher-original Tables 5/6 | ناقص؛ BLOCKED |
| 3 | Car Table 5 74/72 reconciliation | ناقص؛ BLOCKED |
| 4 | Car Table 6 40/41 reconciliation | ناقص؛ BLOCKED |
| 5 | Car groups 4/5 original coding | ناقص؛ BLOCKED |
| 6 | Car 68%/50% source discrepancy | ناقص؛ BLOCKED |
| 7 | Car influence percentages original respondent frame | ناقص؛ BLOCKED |
| 8 | Amini F7 unrounded values and -0.1 discrepancy | ناقص؛ BLOCKED |
| 9 | Cvejić per-question denominator | ناقص؛ BLOCKED |
| 10 | Cvejić 46 email users vs 35 farms | ناقص؛ BLOCKED |
| 11 | Lorite full methods and event-level source | ناقص؛ BLOCKED |
| 12 | Baroni full methods and interview frame | ناقص؛ BLOCKED |
| 13 | Elia full methods and plot measurement | ناقص؛ BLOCKED |
| 14 | G/D/R/A field validation | ناقص؛ BLOCKED |
| 15 | MR independent human-author scientific review | ناقص؛ BLOCKED |
| 16 | MR exact-version publication decision | ناقص؛ BLOCKED |
| 17 | AE C13/C14 recovery | قبلاً تکمیل‌شده؛ این نوبت موفق جدید نیست |
| 18 | AE WDI 2024 original archive bytes and SHA | ناقص؛ BLOCKED |
| 19 | AE WDI 2025 original archive bytes and SHA | ناقص؛ BLOCKED |
| 20 | AE WDI 2026 original archive bytes and SHA | ناقص؛ BLOCKED |
| 21 | AE original-series unit/base-year comparability | ناقص؛ BLOCKED |
| 22 | AE ILOSTAT current/historical independent provenance | ناقص؛ BLOCKED |
| 23 | AE same-source dependency adjudication | ناقص؛ BLOCKED |
| 24 | AE direct countryatlas historical benchmark | ناقص؛ BLOCKED |
| 25 | AE journal-ready original research package | ناقص؛ BLOCKED |

## Y/25 — ZM, CV, staging and MOJ1
| # | Work item | New-run result |
|---:|---|---|
| 1 | ZM exact RefSeq v2.0 FASTA/GTF and licensing | ناقص؛ BLOCKED |
| 2 | ZM reference bytes and SHA-256 | ناقص؛ BLOCKED |
| 3 | ZM biological-replicate independence | ناقص؛ BLOCKED |
| 4 | ZM 48 true FASTQ MD5 checks | ناقص؛ BLOCKED |
| 5 | ZM strandedness evidence | ناقص؛ BLOCKED |
| 6 | ZM multimapping assignment policy | ناقص؛ BLOCKED |
| 7 | ZM full integer count matrix | ناقص؛ BLOCKED |
| 8 | ZM real DESeq2 model | ناقص؛ BLOCKED |
| 9 | ZM valid DEG/FDR result | ناقص؛ BLOCKED |
| 10 | ZM manuscript and author approval | ناقص؛ BLOCKED |
| 11 | CV English v3: repaired evidence links, updated source and qualified owner claims | موفق؛ READY_FOR_REVIEW |
| 12 | CV Persian v3: repaired evidence links, updated source and qualified owner claims | موفق؛ READY_FOR_REVIEW |
| 13 | English HTML noindex staging candidate | موفق؛ READY_FOR_REVIEW |
| 14 | Persian HTML noindex staging candidate | موفق؛ READY_FOR_REVIEW |
| 15 | External academic-degree proof | ناقص؛ BLOCKED |
| 16 | External corporate role and residence proof | ناقص؛ BLOCKED |
| 17 | Verified peer-reviewed bibliography / DOI claims | ناقص؛ BLOCKED |
| 18 | Future topics originality/data/licensing entry gate | ناقص؛ NOT_DONE |
| 19 | Owner approval of exact CV versions | ناقص؛ BLOCKED |
| 20 | S-01 staging-server deployment and public-site release gate | ناقص؛ NOT_DONE |
| 21 | MOJ1 new contract code/security verification | ناقص؛ NOT_DONE |
| 22 | MOJ1 sponsor or Guardian Grants verified response | ناقص؛ NOT_DONE |
| 23 | MOJ1 independent signed audit | ناقص؛ BLOCKED |
| 24 | MOJ1 private artifact 12406875421 archived | قبلاً تکمیل‌شده؛ خارج از شمارش |
| 25 | MOJ1 legal authorization to launch | ناقص؛ BLOCKED |

**Count:** X=1 new substantive correction, 23 incomplete and 1 previously completed C13/C14 recovery not recounted; Y=4 new substantive deliverables, 20 incomplete and 1 previously completed MOJ1 private archive not recounted. **Total=5/50 new, 43 incomplete, 2 historical done not recounted; zero new failures recorded.** The two previously completed items occupy slots only; this cycle did not re-perform them.

## Stage and safety ledger
- **MR-2026-001:** MAJOR REVISION → MAJOR REVISION (C76 v11 READY_FOR_REVIEW); source Car Table 5/6, Amini F7, Cvejić item N, full Lorite/Baroni/Elia and G/D/R/A empirical evidence still BLOCKED. No human author approval.
- **AE-2026-001:** MAJOR REVISION → unchanged. C13/C14 and WDI archive locator are previously completed, not new; actual 2024/2025/2026 WDI bytes/SHA, historical ILOSTAT, same-source sensitivity and direct countryatlas benchmark remain open.
- **ZM-R01:** DATA REBUILD → unchanged. No 149.54 GB download, VPS work, FASTQ hash revalidation, integer count matrix or DEG/FDR result.
- **CV FA/EN:** v3 review candidates available with corrected links; degree/role/publication proof and exact-version owner approval still BLOCKED.
- **Web:** two static HTML staging *source candidates* created in GitHub only; no staging-server deployment, no live-site changes, no backup/rollback trigger, no PR #1054 merge, no prohibited social interaction.
- **MOJ1:** private artifact 12406875421 already archived in #853 (historical, not a new action); independent signed audit, sponsor and legal launch gates remain BLOCKED. No payment, token deploy, sale or agreement.

**DELIVERED external/public result:** 0. **READY_FOR_REVIEW usable research/CV artifacts:** 5 substantive outputs; **approved final manuscripts:** 0; **journal submissions:** 0; **stage transfers:** 0.

**First exact next action:** obtain an authenticated publisher-original Car Table 5/6 or author erratum, reconcile the item-specific utility numerator and the 74/72 / 40/41 contradictions. If unavailable, keep disputed counts quarantined and advance full-methods review of Lorite/Baroni/Elia. S-01 may inspect the two HTML previews, but must not deploy without owner-specific release approval, backup and rollback.

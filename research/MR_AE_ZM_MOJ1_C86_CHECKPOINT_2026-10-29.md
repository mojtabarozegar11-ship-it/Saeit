# R-01 / C86 — 2026-10-29 — substantive MR methodological and provenance corrections

**run_id:** `R-01-C86-20261029T0117+0330` | **branch:** `research/mr-2026-001-novelty-audit` | **WIP:** MR reviewer-ready science pack + bilingual CV (2). **Stage:** READY_FOR_REVIEW, not an approved final article. No journal submission, payment, contract, token launch, public deployment or social-media interaction.

## One usable revised manuscript and five independent substantive changes

1. **Missing-action misclassification repaired:** Verified receipt with independently established absence of the prescribed action throughout an adequately observed prespecified window now counts as **D (verified departure)**. Missing sensor records/diaries remain **U (unknown)**. Earlier D definition counted only an out-of-tolerance measured action and could leave a genuinely observed zero-action event unclassified.
2. **Secondary denominator clarified:** `I/(I+D)` is explicitly **receipt-and-action-resolved conditional**, not the misleading “complete-adjudication fraction”; verified nonreceipt B is adjudicated but intentionally excluded from this conditional denominator. The issued-population bounds `[I/N,(I+U)/N]` remain conceptual and require N=I+D+B+U.
3. **New Car provenance conflict added to main manuscript:** The author-uploaded Table 5 reports **17** “Never sent” whereas the [UNE institutional abstract](https://researchers.une.edu.au/en/publications/using-a-mobile-phone-short-messaging-service-sms-for-irrigation-s-5/) reports **14** never-reporters; original publisher table and individual records still needed. No replacement number invented.
4. **Cvejić frame conflation corrected:** The 35 farms expressing interest in 2016 are now explicitly separated from the abstract's 35 implementation farms and dated survey respondents in the evidence matrix. No item-specific N inferred.
5. **Eight-case selection transparency added:** A source-limited, eight-row **post hoc editorial rationale** now explains why each case appears and why Lorite/Ara are contextual prior art, while expressly rejecting PRISMA/systematic-search claims and post hoc masquerading as preregistration.

The author decision pack was synchronized to these changes; English and Persian CV research citations were aligned to the new manuscript version **without claiming new academic credentials or counting the synchronization as additional scientific work**.

## Recoverable evidence and exact Git blob SHA-1

| Artifact | Link | Before SHA | After SHA | Status |
|---|---|---|---|---|
| MR complete manuscript C86 v12 | [read](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/MR-2026-001/MR-2026-001_C76_CAR_INFLUENCE_CLAIM_DENOMINATOR_AUDIT_MANUSCRIPT_2026-10-28.md) | `643a4cd20b524fa804b7c24a5a5c531dbf0d9ef9` | `ecc438dc46c33dbffa972f8b2ee33bbf01456f74` | READY_FOR_REVIEW |
| MR author decision pack | [read](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/MR-2026-001/MR-2026-001_C78_CORRECTED_SOURCE_TO_CLAIM_AUTHOR_DECISION_PACK_2026-10-28.md) | `42c370a922d58935d51ee12e6252fa321e206978` | `c20c3bc4f5fc28c461a20e6080cd0ed43976d01c` | READY_FOR_REVIEW |
| CV English review copy | [read](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/profile/cv/MOJ_ROOZEGAR_CV_EN_2026-10-29_v3_REVIEW_ONLY.md) | `56f8223ee52759ac748be30cb20f9168dce39f6a` | `1b653c536d295b1be8fa4635fa3d474ed3789772` | READY_FOR_REVIEW; no new credential proof |
| CV Persian review copy | [read](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/profile/cv/MOJ_ROOZEGAR_CV_FA_2026-10-29_v3_REVIEW_ONLY.md) | `c8c78de500768a8fad36276f89e3e17be36a2dcd` | `1a48166c46d5d263a9ca88cd4100b013af254c31` | READY_FOR_REVIEW; no new credential proof |

**Reproducible read-back checks:** Fetch the four paths at `research/mr-2026-001-novelty-audit`; verify the above Git blob SHAs; in the manuscript search for `absence of the prescribed action`, `receipt-and-action-resolved conditional fraction`, `Table 5 **17**`, `35 farms initially expressing interest` and `Transparent post hoc case-selection rationale`. Verify eight selection rows. Check 26+7+3+6+15+17=74 versus printed 72, and 45+13+14=72. The exact branch read-back passed **12/12 editorial/integrity checks**. These checks are not independent human review, empirical validation, or production tests. Commits: `ff341eaa97a1a290009335447eeb283b0ce155a1`, `e768b7b597ceb773772834be0658288f00b48c94`, `9ce276a4470c5d3b2e652d74cc0308db5daa861a`, plus CV reference-sync commits.

## X/25 — MR and AE
| # | Independent target | This run |
|---:|---|---|
| 1 | Verified receipt + observed absence of prescribed action: classify as D, not U | موفق؛ READY_FOR_REVIEW |
| 2 | Rename I/(I+D) to receipt-and-action-resolved conditional estimand; B exclusion explicit | موفق؛ READY_FOR_REVIEW |
| 3 | Add Car Table 5 never-sent 17 versus UNE abstract 14 contradiction | موفق؛ READY_FOR_REVIEW |
| 4 | Separate Cvejić 2016 interested farms from abstract implementation and survey cohorts | موفق؛ READY_FOR_REVIEW |
| 5 | Add eight-case post hoc editorial selection rationale and limitations | موفق؛ READY_FOR_REVIEW |
| 6 | Car publisher-authenticated original Tables 5/6 | ناقص؛ BLOCKED |
| 7 | Car Table 5 74 versus 72 and category order | ناقص؛ BLOCKED |
| 8 | Car Table 6 41 versus 40 and perceived influence | ناقص؛ BLOCKED |
| 9 | Car prose 68% versus 50% | ناقص؛ BLOCKED |
| 10 | Amini F7 raw precision and -0.1 claim | ناقص؛ BLOCKED |
| 11 | Cvejić per-question response denominator | ناقص؛ BLOCKED |
| 12 | Cvejić 2019 46 email users versus 35 farms | ناقص؛ BLOCKED |
| 13 | Lorite full methods and unit-level observation | ناقص؛ BLOCKED |
| 14 | Baroni full methods and end-user frame | ناقص؛ BLOCKED |
| 15 | Elia full methods and plot allocation | ناقص؛ BLOCKED |
| 16 | G/D/R/A field validation and coder reliability | ناقص؛ BLOCKED |
| 17 | Human author's substantive scientific review | ناقص؛ BLOCKED |
| 18 | Final MR exact-version approval and journal gate | ناقص؛ BLOCKED |
| 19 | AE C13/C14 recovery | تکمیل قبلی؛ شمارش نشد |
| 20 | AE WDI 2024 archive original bytes/SHA | ناقص؛ BLOCKED |
| 21 | AE WDI 2025 archive original bytes/SHA | ناقص؛ BLOCKED |
| 22 | AE WDI 2026 archive original bytes/SHA | ناقص؛ BLOCKED |
| 23 | AE ILOSTAT historical and shared-source audit | ناقص؛ BLOCKED |
| 24 | AE direct countryatlas benchmark | ناقص؛ BLOCKED |
| 25 | AE scientific manuscript and author package | ناقص؛ BLOCKED |

## Y/25 — ZM, CV, staging, MOJ1
| # | Independent target | This run |
|---:|---|---|
| 1 | ZM exact RefSeq v2.0 FASTA/GTF and licensing | ناقص؛ BLOCKED |
| 2 | ZM reference byte-level checksum | ناقص؛ BLOCKED |
| 3 | ZM independent biological replicate evidence | ناقص؛ BLOCKED |
| 4 | ZM 48 real FASTQ MD5 checks | ناقص؛ BLOCKED |
| 5 | ZM strandedness evidence | ناقص؛ BLOCKED |
| 6 | ZM multimapping policy | ناقص؛ BLOCKED |
| 7 | ZM complete raw integer counts | ناقص؛ BLOCKED |
| 8 | ZM actual DESeq2 run | ناقص؛ BLOCKED |
| 9 | ZM valid DEG/FDR result | ناقص؛ BLOCKED |
| 10 | ZM manuscript and author approval | ناقص؛ BLOCKED |
| 11 | CV EN C86 link metadata sync (QA only; no new substantive output) | ناقص؛ نسخه تازه تأیید نشده |
| 12 | CV FA C86 link metadata sync (QA only; no new substantive output) | ناقص؛ نسخه تازه تأیید نشده |
| 13 | English staging HTML server deployment | ناقص؛ NOT_DONE |
| 14 | Persian staging HTML server deployment | ناقص؛ NOT_DONE |
| 15 | Academic-degree independent proof | ناقص؛ BLOCKED |
| 16 | Corporate role and residence independent proof | ناقص؛ BLOCKED |
| 17 | Peer-reviewed bibliography independently verified | ناقص؛ BLOCKED |
| 18 | Future-topic data/novelty/rights gate | ناقص؛ NOT_DONE |
| 19 | Owner approval of exact CV versions | ناقص؛ BLOCKED |
| 20 | S-01 coordinated release with backup/rollback | ناقص؛ NOT_DONE |
| 21 | MOJ1 new contract/security progress | ناقص؛ NOT_DONE |
| 22 | MOJ1 sponsor / Guardian Grants reply | ناقص؛ NOT_DONE |
| 23 | MOJ1 signed independent audit | ناقص؛ BLOCKED |
| 24 | MOJ1 private audit artifact 12406875421 | تکمیل قبلی؛ شمارش نشد |
| 25 | MOJ1 legal authorization to launch | ناقص؛ BLOCKED |

**New substantive count:** X=5, Y=0, total **5/50**. **Incomplete:** X=19, Y=24, total **43**. **Previously completed, not counted:** X=1 (AE C13/C14), Y=1 (MOJ1 archive), total 2. **New verified failures:** 0. CV reference sync, tests, commits, issue comments and this checkpoint are not counted as new independent scientific actions.

## Stage transfer and safety

| Project | Before → After | New stage transfer | Gate |
|---|---|---:|---|
| MR-2026-001 | MAJOR REVISION → MAJOR REVISION (C86 v12 READY_FOR_REVIEW) | 0 | Car publisher original, Amini F7, Cvejić response N, full Lorite/Baroni/Elia methods, validation and author sign-off |
| AE-2026-001 | MAJOR REVISION → unchanged | 0 | Original 2024/2025/2026 WDI ZIP bytes/SHA, ILOSTAT vintages, independent benchmark |
| ZM-R01 | DATA REBUILD → unchanged | 0 | RefSeq v2.0 exact bytes, 48 FASTQ MD5, 24-library raw integer counts and legitimate DESeq2 |
| CV EN/FA | READY_FOR_REVIEW → updated reference labels only | 0 | External credential and role evidence, owner approval |
| Web staging | GitHub HTML source candidates only → unchanged | 0 | No server deployment; S-01 release ownership, backup and rollback |
| MOJ1 | BLOCKED → unchanged | 0 | Independent audit, sponsor, legal approval |

**DELIVERED approved final papers:** 0. **Journal submissions:** 0. **New public/site deployments:** 0. **External commercial results:** 0. No 149.54GB ZM download, VPS changes, PR #1054 merge, prohibited Instagram/Facebook activity or token actions.

**First exact next action:** Obtain and authenticate publisher-original Car Table 5/6 or an author erratum and adjudicate the 17/14, 74/72 and 41/40 source conflicts; if inaccessible, preserve quarantine and continue full-methods checks for Lorite/Baroni/Elia. No paper submission until exact-version human author and legal/disclosure gates are explicitly approved.

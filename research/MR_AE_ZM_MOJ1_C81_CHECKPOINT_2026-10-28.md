# R-01 / C81 — substantive Car group crosswalk and Cvejić respondent-frame correction

**run_id:** R-01-20261028T2010+0330-C81  
**Scope:** Existing MR working manuscript and exact-version author decision pack only; WIP ≤2, no production, no manuscript submission.  
**Carryover:** [Shared issue #1514](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514), [C80 checkpoint](MR_AE_ZM_MOJ1_C80_CHECKPOINT_2026-10-28.md).  
**Status:** **READY_FOR_REVIEW** for MR author-review manuscript; **DELIVERED final article: NO**.

## Two independent substantive scientific advances

1. **Car 2012: resolve the *internal* five-group crosswalk at semantic, not publisher-authenticated, level.** The [author-uploaded typeset article](https://www.researchgate.net/publication/257018309_Using_a_mobile_phone_Short_Messaging_Service_SMS_for_irrigation_scheduling_in_Australia_-_Farmers%27_participation_and_utility_evaluation), printed pp. 140–142, first defines five Table 6 behavioral classes (Small=11, Large=10, Significant=9, None=8, Marginal=3). Its immediately following discussion numbers five groups: #1 confidence/little change → Small; #2 increased irrigation on trust → Large; #3 change magnitude not articulable → Significant; #4 rejected excessive advice → None; #5 educational interest without changed action → Marginal. This **semantic mapping** independently supports the existing arithmetic: (10+9)/41=46.341%, (10+9+11)/41=73.171%, (10+9+11+3)/41=80.488%. **Before C81:** numerical coincidence only, category crosswalk unresolved. **After C81:** strong *source-internal* crosswalk, with the **40-in-prose vs 41-in-table discrepancy still open**. Neither a corrected denominator nor an objective adherence measure has been established. Separate Table 5: counts 74 vs printed total 72, 4/5 labels reversed, prose 68% vs 36/72=50%; no corrections fabricated.
2. **Cvejić 2020: split historically distinct respondent frames.** The [publisher full text](https://www.mdpi.com/2073-4395/10/9/1238) describes **35 interested farms at 2016 recruitment**, **38.5 ha included after participation agreements**, **2019 first-experience responses from 66% of 'our farmers'**, a literal **2019 '46 farmers use e-mail advice'** statement, and **2020 three-weekly telephone feedback (83% reporting IDSS use; 71% soil-moisture viewing)**. Earlier drafts did not explicitly distinguish the 2016, 2019 and 2020 frames. **After C81:** no longitudinal N is inferred from recruitment counts; 46 is quarantined, not silently converted to 46% or a separate cohort; the 25% volume-saving result is a conditional model scenario, not measured realized saving. The source also reports **91% of farmers did not regularly record diary actions**, an explicit missingness caveat.

## Versioned verified artifacts

- [MR manuscript C76 v7](manuscripts/MR-2026-001/MR-2026-001_C76_CAR_INFLUENCE_CLAIM_DENOMINATOR_AUDIT_MANUSCRIPT_2026-10-28.md) — Git blob SHA **38e5f78560969667db9f5aae4a9fb7bf532a1d2f**; material commits [2ee39a2](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/2ee39a2e97d21eb32000d2941571f0676318bc8d), [6e0d8be](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/6e0d8be7b071416c7749e69070569043812bbfb7), and coherence edit [048d311](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/048d3115a3ddffd15df359ebf18f097d42a74aa9).
- [MR eight-study author decision pack C78 updated for C81](manuscripts/MR-2026-001/MR-2026-001_C78_CORRECTED_SOURCE_TO_CLAIM_AUTHOR_DECISION_PACK_2026-10-28.md) — Git blob SHA **9f4cea19e3aba508021c3fc5e723a88d5ba7eb8b**; commits [9998877](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/99988777b9b3f5a9468af5936ef1fc6bf5dcea66), [2653400](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/265340069bf9e95051eed54988123b6380371dbc).
- Both files re-fetched from the requested branch after final writes and exact Git blob SHA matched. No claim of independent publisher-version verification.

## Reproducible arithmetic checks

```js
const t5=[26,7,3,6,15,17], t6=[11,10,9,8,3];
const sum=a=>a.reduce((x,y)=>x+y,0);
console.assert(sum(t5)===74 && sum(t6)===41);
console.assert([19,30,33].every((n,i)=>Math.round(n/41*100)===[46,73,80][i]));
console.assert(45+13+14===72);
```

The checks validate **published aggregate arithmetic**, not biological, agronomic or questionnaire validity.

## Remaining gates and priority carryover

- **MR Major Revision:** Publisher-authenticated Car table and 40/41 correction, Table 5 74/72 and group 4/5; Amini F7 conflicting prose/table; Cvejić exact 2019/2020 survey response ledgers; complete Lorite/Baroni/Elia methods; real G/D/R/A validation or expressly conceptual framing; human author substantive review and exact-version approval. **No submission.**
- **AE Major Revision:** C13/C14 prior artifacts not counted new; historical WDI ZIP bytes, SHA and unit metadata, independently archived ILOSTAT releases, real countryatlas benchmark and novelty evidence still missing. Official [WDI archive gate](manuscripts/AE-2026-001/AE-2026-001_WDI_OFFICIAL_ARCHIVES_PROVENANCE_GATE_2026-10-28.md) inspected, but historical files not downloaded.
- **ZM Data Rebuild:** Exact licensed IWGSC RefSeq v2.0 FASTA/GTF/checksums, independent 24 biological samples and 48 FASTQ MD5, valid integer count matrix and DESeq2/FDR still missing; no VPS/149.54GB download.
- **FA/EN CV:** Existing [FA v1](profile/cv/MOJ_ROOZEGAR_CV_FA_2026-10-28_v1_REVIEW_ONLY.md) and [EN v1](profile/cv/MOJ_ROOZEGAR_CV_EN_2026-10-28_v1_REVIEW_ONLY.md) fetched and checked as owner-claim-qualified; no newly authenticated degree, publication, office or new approved CV. No staging/live site change.
- **MOJ1:** [#853](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/853) remains NO-GO and [#1395](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1395) funding uncommitted. Private audit artifact 12406875421 **previously archived and verified**; do not count again. Gmail search through 2026-10-28 found no new confirmed grant or independent signed audit. No emails sent, payments, token transfers or deployments.

**New independent scientific actions:** **2** (Car source-internal semantic crosswalk; Cvejić 2016/2019/2020 respondent-frame correction). Updating two documents and multiple commits does not create extra independent actions. **New material output:** 1 updated, source-grounded manuscript + matching author decision pack, **READY_FOR_REVIEW**; **DELIVERED approved article: 0**; **article stage transfers: 0**; **submission: 0**. Five-action minimum not met; do not invent remaining 3.

**First exact next action:** obtain the actual Car 2012 Elsevier version-of-record Table 5/6 pages or author clarification to verify the source-internal mapping and correct 40/41, then inspect the Cvejić original 2019 and 2020 response ledgers; do not convert 46 to a percentage without an author correction. Maintain no more than two WIP deliverables.

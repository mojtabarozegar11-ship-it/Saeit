# R-01 / C82 — non-prescriptive advice and adherence identifiability correction

**run_id:** R-01-20261028T2109+0330-C82
**Scope:** Existing MR-2026-001 working manuscript and author decision pack; WIP=1; no live site, VPS, publication, payments, MOJ1 deployment or external commitment.
**Carryover:** [Shared R-01 issue #1514](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514); [C81 checkpoint](MR_AE_ZM_MOJ1_C81_CHECKPOINT_2026-10-28.md).
**Stage:** **READY_FOR_REVIEW** (source-qualified scientific manuscript and author decision pack); final human-approved article **NOT_DONE**.

## Two new independent substantive actions (not commit/test counts)

1. **Original-source Car decision-behavior extraction:** Read the [author-uploaded Car et al. 2012 text, printed pp. 139 and 142](https://www.researchgate.net/publication/257018309_Using_a_mobile_phone_Short_Messaging_Service_SMS_for_irrigation_scheduling_in_Australia_-_Farmers%27_participation_and_utility_evaluation). Source says 25% accumulated suggested dripper run-time minutes over several days, and 79% combined multiple information sources; exact item-specific response denominators were not authenticated. More importantly, Discussion §4.2 states the service did **not stipulate when to irrigate or the amount**. **Before:** C81 manuscript did not explicitly extract these decision-process findings or differentiate non-prescriptive advice from actionable orders. **After:** C76 v8 §3.5 adds qualified 25%/79% and non-prescriptive advisory semantics, with source locator and no invented respondent counts or compliance effect.
2. **Conceptual event-estimand correction with author-ready text:** A non-prescriptive informational message has no uniquely specified irrigation action target, so coding it as `implemented=0/1` is undefined rather than a farmer failure. **Before:** the C74 issued-event `N=I+D+B+U` definition was not explicitly restricted by actionability, risking contamination by non-prescriptive messages. **After:** C76 v8 §§5.1 and 5.3 distinguish prescriptive, conditional and informational messages, restrict event-level adherence to actionable eligible recommendations, define `NOT_DEFINED` and `UNKNOWN_ADVICE_TYPE` for missing targets, and preserve a separate informational-exposure denominator. C78 author pack adds a complete corrected paragraph and explicit decision gate. This is a proposed, unvalidated method; no field validation, observed adherence or causal water savings claimed.

These are **two** distinct scientific corrections; updating two files, multiple commits and seven structural assertions do **not** inflate the action count.

## Recoverable artifacts and immutable evidence

- [C76 MR working manuscript v8](manuscripts/MR-2026-001/MR-2026-001_C76_CAR_INFLUENCE_CLAIM_DENOMINATOR_AUDIT_MANUSCRIPT_2026-10-28.md), Git blob **a3611802563ce593c02f1ae87a0c939f9c72d8f0**; material commit [2d637b0](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/2d637b07ad0f8a0cbbeaa7dcc6e9830d7ddd0c50); coherent section/estimand follow-up [c5678ce](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/c5678cea4a7ee864a98375d0a09c8e99d640458e).
- [C78 MR author decision pack, C82 updated](manuscripts/MR-2026-001/MR-2026-001_C78_CORRECTED_SOURCE_TO_CLAIM_AUTHOR_DECISION_PACK_2026-10-28.md), Git blob **73849f57a5c580ed0c8b00c3a171caa8aa586582**; material commit [f8c5482](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/f8c548206858d5b4ed715322ebe150e3eddeaf4a).
- Independent source: [Car author-uploaded full text](https://www.researchgate.net/publication/257018309_Using_a_mobile_phone_Short_Messaging_Service_SMS_for_irrigation_scheduling_in_Australia_-_Farmers%27_participation_and_utility_evaluation), pp. 139, 142. Publisher-authenticated original table images and survey ledgers still **not** obtained. [UNE abstract](https://rune.une.edu.au/entities/publication/68f9d1ef-6e62-415a-b831-0beb96df9853) independently confirms 45+13+14=72 participation categories but not the new 25%/79% item Ns.

## Reproducibility / QA

Both files were **re-fetched from the requested branch after the final writes** and Git blob SHA matched the values above. Seven structural checks passed: (1) both contain C82 correction; (2) manuscript v8/pack v8 cross-reference; (3) both include qualified 25%/79%; (4) both explicitly preserve item-N uncertainty; (5) manuscript sections 5.1, 5.2, 5.3, 6 in order; (6) no empirical savings or experimental claims; (7) internal project identifier not presented as journal manuscript ID.

Conceptual logic checks, not data tests:
```js
function classifyAdvice({target,window,trigger,response}) {
  if (target && window) return 'PRESCRIPTIVE';
  if (trigger && response) return 'CONDITIONAL';
  return 'INFORMATIONAL_OR_UNDETERMINED';
}
console.assert(classifyAdvice({target:null,window:null,trigger:null,response:null}) === 'INFORMATIONAL_OR_UNDETERMINED');
console.assert(classifyAdvice({target:'12mm',window:'48h'}) === 'PRESCRIPTIVE');
// Without an explicit actionable target, adherence must be NOT_DEFINED, never zero.
```

## Remaining article and parallel-project gates

- **MR Major Revision:** Car Table 5 74/72, group 4/5 reversal, 68% vs 50%, Table 6 40/41, publisher original; Amini F7 -1.4/-1.3/-0.1; Cvejić exact item Ns and 46-email statement; full Lorite/Baroni/Elia methods; prospective G/D/R/A validation; human author's substantive decisions, identity, COI/AI, funding, rights, journal/APC and exact-version approval. **No submission.**
- **AE Major Revision:** Historical WDI archive bytes/SHA and per-vintage units, historical ILOSTAT snapshots, source dependence, actual countryatlas benchmark, novelty. Prior C13/C14 analyses are old and not counted new; fresh exact artifact retrieval still pending.
- **ZM Data Rebuild:** licensed exact IWGSC RefSeq v2.0 FASTA/GTF/checksums, 48 real FASTQ MD5s, verified sample independence, integer count matrix and DESeq2/FDR. FPKM and 1,167 exploratory hypotheses are not DEG/FDR; no 149.54GB bulk download.
- **CV:** Existing FA/EN review-only drafts retained; no new independently authenticated credentials or publications. **No staging or live website changes.**
- **MOJ1:** Independent signed audit, actual sponsor funding and legal deployment approvals still **BLOCKED**. Private artifact 12406875421 was already archived/verified and is **not** a new action. No external email, commitment, payment, deployment or token sale.

**New substantive actions: 2. New verified usable review-stage output: 1 paired MR manuscript + author pack (READY_FOR_REVIEW). Final approved articles: 0; journal submissions: 0; stage transfers: 0.** Minimum five-action target missed by 3; do not invent them. Remaining 48 of 50 target slots not claimed as completed.

**First exact next action:** Compare the C82 actionable-advice definition against original Lorite 2012 and Baroni 2019 methodological descriptions, if accessible; explicitly exclude abstract-only inference. Then resolve or quarantine the oldest source conflict in Car (publisher-original Table 5/6) and prepare a conservative author decision on whether to omit all disputed denominators. Continue MR rather than open a new future-topic manuscript.

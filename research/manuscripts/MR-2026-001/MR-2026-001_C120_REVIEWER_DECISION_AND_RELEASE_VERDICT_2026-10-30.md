# MR-2026-001 — C120 independent reviewer decision pack and release verdict
Date: 2026-10-30. **Status: READY_FOR_REVIEW; NOT SUBMITTED.** Scope: critical narrative review, not systematic review or empirical validation.

## Material actually checked
- Full manuscript read back from GitHub branch: [C120 author-review manuscript](../MR-2026-001_C120_CLEAN_SOURCE_ADJUDICATED_AUTHOR_REVIEW_MANUSCRIPT_2026-10-30.md); GitHub blob SHA `84c57954ab0391b6f454da5dece65f06b622540f`, 126826 characters. A Git blob SHA is **not** an independently calculated SHA-256 of downloaded bytes.
- Source-to-claim table read back: [C120 evidence ledger](../MR-2026-001_C120_CAR_ORIGINAL_TABLE_GROUP_CLAIM_LEDGER_2026-10-30.tsv); 8 rows, 6 explicit BLOCKED entries.
- Source rechecked: Car et al. 2012 author-uploaded original §3.4, Tables 5–6, pp. 139–141; UNE institutional abstract. Source links in ledger.
- Automated offline gate [r01_submission_gate_C120.py](../../quality_gates/r01_submission_gate_C120.py) was locally syntax-checked and fail-closed behavior tested on a synthetic three-row fixture (exit code 2). **It has not been executed on this complete GitHub manuscript in a verified checkout**, so no real-manuscript CLI PASS is claimed.

## Reviewer decisions and exact required revisions
| Issue | Original-source finding | Editorial disposition | Remaining dependency |
|---|---|---|---|
| Car group ordinals | §3.4 calls group 4 Stopped, group 5 Less; Table 5 prints row 4 Much less (6), row 5 Stopped (15) | Correct manuscript §3.5 to refer to named categories, not group number; inserted in C120 | Person-level roster absent |
| Car Table 5 arithmetic | 26+7+3+6+15+17=74, printed total 72 | Exclude participant prevalence and preserve discrepancy | Publisher erratum or author data |
| Car stopped-group subfraction | Prose says 7/12, table stopped 15 | Do not reconcile by guessing; retain source warning | Group-specific original denominator |
| Car Table 6 arithmetic | 11+10+9+8+3=41, percentages agree with 41; prose says 40 respondents | Explain percentage denominator as printed **assignments**, not verified people; inserted in C120 | Original survey roster |
| Amini F7 | Rounded table/figure/text differences conflict | Preserve ranges; do not invent exact estimate | Original unrounded values |
| Cvejić | 35 implementation farms vs distinct respondent frame | Keep item/area/energy model denominators separate | Item-level questionnaire counts |
| Baroni | Publisher lists supporting file but content not read | Do not claim supplement validated event-level data | Authenticated supplement access |

## Publication release verdict
**BLOCK_SUBMISSION.** Structural sections present: true; full manuscript retains 62 internal version tags and requires a separate journal-facing copy-edit. Source issues: 6 blocked ledger rows. Human authorship/affiliation/contributions, ethics/rights/COI, journal fit, exact-version author approval, verified bibliography and external submission receipt are not established. No submission, DOI, acceptance, public publication or journal fee authorized.

## Exact offline invocation after a verified Git checkout
```bash
python3 research/quality_gates/r01_submission_gate_C120.py \
  --manuscript research/manuscripts/MR-2026-001/MR-2026-001_C120_CLEAN_SOURCE_ADJUDICATED_AUTHOR_REVIEW_MANUSCRIPT_2026-10-30.md \
  --ledger research/manuscripts/MR-2026-001/MR-2026-001_C120_CAR_ORIGINAL_TABLE_GROUP_CLAIM_LEDGER_2026-10-30.tsv \
  --output /tmp/mr-c120-qc.json
```
Expected current result: exit 2, BLOCK_SUBMISSION. Never fabricate an author approval JSON. Once source issues are editorially adjudicated, run human source audit, independent review and journal requirements before asking for exact manuscript submission approval.

**First next action:** remove remaining internal version labels from a journal-facing manuscript without changing scientific meaning; have a second reviewer verify Car §3.4 source/table claims and the full reference list. Keep factory VPS and master agent untouched.

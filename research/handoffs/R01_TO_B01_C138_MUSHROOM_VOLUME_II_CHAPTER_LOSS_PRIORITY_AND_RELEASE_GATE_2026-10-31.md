# R-01 → B-01: Mushroom EN Volume II — independent provenance-loss risk prioritization

**Date:** 2026-10-31 | Owner of this handoff: R-01 | Receiving owner: B-01 | Stage: READY_FOR_REVIEW, NOT publication approval

## Grounded inputs and independent calculation

Inputs are the **B-01 checkpoint in issue #1514, 2026-10-31**; this handoff has **not** accessed the owner-private C113/R18 book binaries or any unpublished customer records.

| Measure | Reported by B-01 | R-01 calculation / interpretation |
|---|---:|---|
| C113 paragraph-split words | 223,079 | Baseline only; not verified against source bytes here |
| R18 paragraph-split words | 199,305 | Net difference **−23,774** |
| Chapter 20 net reduction | 14,012 | **58.94%** of total net reduction |
| Chapter 18 net reduction | 5,465 | **22.99%** |
| Chapter 19 net reduction | 3,623 | **15.24%** |
| Three-chapter combined net reduction | 23,100 | **97.16%** of total net reduction |
| Other 12 chapters combined net change | −674 | Net only; may mask both additions and removals |

**Inference limit:** The large reductions do **not** by themselves prove errors, plagiarism, rights violations or missing scientific facts. They **do** justify mandatory paragraph-level source, numerical, safety and teaching-content reconciliation before commercial publication.

## Release-review gate to apply to B's existing private 1,001-change / 1,207-risk inventories

1. **Ch20 (highest priority):** map each deleted/rewritten high-risk claim to its old/new paragraph, primary citation, jurisdiction and evidence type; specifically prevent treating zero observed incidents as proof of zero risk, and do not promote unverified OSHA/food-safety legal scope.
2. **Ch18:** adjudicate every removed numerical, worked-example, figure-reference and source-bearing passage; recompute retained formulae with units, discount period and explicit hypothetical inputs.
3. **Ch19:** independently inspect changed process and economic assertions, citation links and safety caveats; distinguish factual evidence from illustrative assumptions.
4. **Other 12 chapters:** require complete coverage of B's existing change inventory despite only −674 net words; additions can cancel deletions, so net length is not a substitute for diff review.
5. **All 15 chapters:** verify primary-source locator, claim scope, numerical replication, image/media rights, originality and owner authorization. Any unresolved material claim is marked HOLD or excluded; no blanket '15/15 approved' from the arithmetic above.

### Minimal decision-record fields

`chapter | old_paragraph_id | new_paragraph_id | change_kind | source_locator | claim_type | number_unit_check | rights_check | qualified_reviewer | disposition | rationale | reviewer_date`

Allowed disposition: `RETAIN_VERIFIED`, `REWRITE_WITH_SOURCE`, `EXCLUDE_UNVERIFIED`, `BLOCKED_REVIEW`. Empty reviewer fields **must fail** the release gate. No fabricated reviewer identities or approvals.

**Handoff decision:** Chapter-loss prioritization is analytically **READY_FOR_REVIEW**; full source-to-claim inspection, originality/rights signoff, exact-hash author approval and S-01 live purchase→invoice→download verification remain **BLOCKED**. This file is independent R-01 assistance only; no B source, site, factory or VPS files were modified.

**Source checkpoint:** https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514#issuecomment-6536462494

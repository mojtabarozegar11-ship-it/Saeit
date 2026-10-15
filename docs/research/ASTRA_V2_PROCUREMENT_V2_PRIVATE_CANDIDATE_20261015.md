# Astra 2.0 Procurement Quote Normalization V2 — Private Candidate, 15 October 2026

## Scope and actual advancement

The first market-oriented engineering improvement beyond the three existing private Astra prototypes is a **backward-compatible, explicitly specified whole-pack quotation audit**. It addresses the common error of comparing whole-bag supplier prices against per-kilogram prices without accounting for purchase quantities, wastage, order minimums, freight and capacity.

- Added **per_pack** pricing basis and **pack_size_base_units** (both or neither per offer), exact Decimal ceiling of needed whole packs, declared-capacity check against rounded physical quantity, usable purchased units and surplus, normalized indicative list price, and an explicit *arithmetic* gap between eligible supplier totals.
- Existing price-per-base-unit quotations retain exactly the original mathematics. Tax/freight/discount assumptions are kept explicit.
- Updated the offline print-friendly HTML report with quote pricing basis, packs, usable surplus and non-realized price differences, with HTML escaping.
- Added **11 scientific/mathematical regression tests** for package quantities, unused material, minimum lot, capacity constraints, stress case recomputation, unsupported inputs, surplus and no false savings. The independently executable ZIP self-test now verifies a package quote directly.

## Reproducible synthetic numbers

For 100 kg usable material, 5% waste, 20 kg indivisible bags, 90 USD per whole bag, 5% discount, 45 USD freight, zero setup and tax:

| Metric | Demonstration |
| --- | --- |
| Unrounded gross requirement | about 105.26 kg |
| Bags ordered | 6 |
| Gross units purchased | 120 kg |
| Estimated usable units | 114 kg |
| Surplus usable units | 14 kg |
| Material after discount | 513 USD |
| Landed estimate | **558 USD** |

This is **not a real supplier quote** and demonstrates arithmetic, not realized savings or a commercial opportunity. Tax, supplier trustworthiness, packaging returns, chemical equivalence and price validation require separate buyer evidence.

## Verified automated evidence

1. [Integrated code regression run 38689578649](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38689578649): core-model Django check/migration parity and private Astra specialist regression tests SUCCESS on the same 0048/0049 integration branch.
2. [Private VPS candidate construction run 38689677395](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38689677395): 28 procurement tests pass **both** in GitHub runner and on private VPS, prototype self-test passes exact six-bag example, HTML print report compiles, immutable private 5-file ZIP produced with SHA-256 **1c220a585e78076c912204aa73a2cf55c45b14d13f4ae7131f6b3ba538f7e768** and fail-closed QA manifest. Distinct private QA candidate only. Original Django factory remains migration 0048 with 209 products.
3. [Independent read-only follow-up 38689791248](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38689791248): source ZIP/manifest SHA hashes and zipped exact source file list confirmed; source revision matches manifest; source ZIP differs from **unchanged running private procurement builder**, three original QA builder families retained; original factory still 0048 and 209 products, **zero commercial product approvals**.

## What this proof does not claim

- No customer interviews, normalized *real* supplier quotes, regional tax/legal compliance, independent product-spec equivalence or reviewer accreditation are established.
- The improved code resides in a **separate private candidate package**; it did **not** overwrite the running VPS specialist or increment the number of commercially distinct products. It is one **technical revision of one pre-existing family**, not a new family or paid sales item.
- No original factory 0049 cutover, live website publishing, fake list price, 90% discount automation, checkout settlement or revenue was attempted.
- This candidate has **no independent commercial quality score** and must not receive a 90/100 or 100/100 claim from passing software tests.

## Next accept/reject gate

Obtain anonymized genuine farm procurement quotations with consent and documented comparable grade/unit/contract terms; independently compare exact hand-calculated versus engine results, validate the buyer's cost/speed improvement versus a free spreadsheet, obtain a subject-expert review of cost and tax assumptions, and measure actual willingness to pay. Fail to publication-safe private research if any requirement is missing. Only then assess whether to adopt this revision as the running private specialist and create an authorized public retail edition.

**Release status:** PRIVATE_TECHNICAL_CANDIDATE / COMMERCIAL_BLOCKED.


## Later technical promotion to running PRIVATE specialist (same date)

This section supersedes the earlier "candidate not yet running" limitation **only as to the private specialist**. Publication restrictions and unverified commercial demand remain unchanged.

- [First successful private source upgrade 38690111870](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38690111870) used the existing factory locks, copied a recoverable private source backup, installed the revised procurement math and test in the isolated Astra R&D runtime, invoked the actual autonomous private manufacturing pipeline and verified its immutable new ZIP had passed private QA. 28 procurement tests and 31 pipeline tests passed. The original database remained on migration 0048, with no store, payment or publicly deployed site changes.
- [Hardened rollback workflow run 38690177651](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38690177651) succeeded with rollback state maintained in the same shell (guards even partial swaps). Again the source-built procurement revision reached PRIVATE_QA_PASSED, the **three original builder families** remained present and the original factory SQLite SHA was unchanged across the operation.
- It remains only a newer **source revision of the second pre-existing builder family**, not a fourth product family, a commercial launch or a customer transaction. Expert validation, actual procurement quotes, verified buyer problem, source licensing and real financial settlements remain absent.
- The private source backup is retained for rollback. Both PR #101 and #109 continue unmerged/draft as appropriate; only the private isolated canary manufacturing source was updated, never the live commerce/site stack.

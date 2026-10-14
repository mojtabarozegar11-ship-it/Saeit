# Saeit VPS factory — Astra architecture upgrade, 2026-10-14

## Source of truth

This is an **update to the original Astra architecture**, not a parallel factory redesign. Reference: Issue #41 and the original private archive transferred to the authorized VPS. Archive SHA-256: `2333e35dfd29efd807cd98d31388d8a454fe9c9f030d077d7b1f1f2235f546a5`; 42 archive entries.

Original Astra flow:

`Hypotheses → FactoryQueueItem(discovery) → DiscoverySnapshot → Intake → FactoryQueueItem(run) → Existing AgentTask / ToolGateway / Pipeline`

Existing Site/Owner approval, evidence lineage, output checks, and audit logging remain mandatory. The archive was written for a cPanel staging path and references an installer `install.py` **not present in this archive**; therefore do not treat it as a ready-to-apply binary installer.

## Verified current state

- Main VPS loop and watchdog were live in the latest read-only inventory, with cron running and enabled at boot. No direct evidence yet that Stage 4 to Stage 5 is released.
- The independent, order-free digital manufacturing scheduler has successfully built **two QA-tested private products**, and the existing SSH handoff delivered them to the **private** hosting inbox. This is not authorization to list or charge for products.
- VPS isolated research database inventory: 104 FactoryRun (95 blocked, 9 active), 145 AgentTask (95 blocked, 50 completed), 9 inactive candidate products, 14 research Evidence and 14 Findings. Counts are from the 2026-10-14 13:10 UTC read-only inventory; do not present as continuously live counters.
- Against the Astra package: 0 identical, 18 divergent, 11 absent source files in the VPS Django runtime. Current VPS migration reaches `0048_business_market_architecture`, making Astra's `0049_factory_durable_queues` a candidate **only after verification**.
- An isolated disposable VPS source overlay (28 original Astra code files, adapted private settings, a private SQLite backup copy) passed Python compilation, Django checks, the `0049` migration and the isolated queue tests. **None of those operations modified the live factory database or sites.**

## Compatibility update and new input

`factory_assets/astra_initial_200_hypotheses.json` supplies 200 DISTINCT and explicitly **unverified** research questions across 50 economic topics. These are research hypotheses, not evidence, validated opportunities, published products or market claims. The original Astra seed command expects `var/factory/discovery/initial_200_hypotheses.json`; production must receive the checked candidate at this exact private runtime location only during a guarded cutover.

Astra's original `config/factory_local_settings.py` is hard-coded to an earlier cPanel staging path and SQLite location. An approved VPS adaptation must scope it to the **isolated factory database**, require explicit local opt-in, disable all real money/paid LLM/treasury/publication code paths, and refuse to run in the public Django Passenger process. The general public staging/PostgreSQL rules should not be relaxed.

## Gate-by-gate implementation

1. **Read-only provenance (passed):** archive SHA, file inventory, code/model differences, live process and cron audit.
2. **Disposable staging QA (in progress):** versioned seed, schema migration on a private copy, durable queue acceptance tests, health command, seed and maintenance tick, then one bounded research/intake tick with no paid APIs. No fixtures enter live queues.
3. **Regression and adaptation:** reconcile all 18 changed modules, preserve modern safety checks, test owner policy, replay protection, research source provenance, same-publisher content changes, correct run/product selection, lease recovery, and fixed retry budgets. No blind overwrite of `core/models.py` or `core/task_runtime.py`.
4. **Single-writer guarded cutover only after all gates pass:** back up exact files and consistent SQLite snapshot, verify process ownership and shutdown/supervision, apply adapted schema/code under an exclusive lock to the private factory runtime only, run health and one bounded tick, verify persisted evidence; if any check fails, restore the exact code and supervised process. Never migrate, overwrite, delete or publish the websites' actual databases.
5. **Autonomous Stage 5 operation:** default maintenance tick alone performs no research; research/intake must be explicitly bounded. `NO_EVIDENCE` becomes `waiting_for_evidence` (24-hour revisit), not a validated market opportunity. Up to 3 hypotheses per discovery tick, up to 8 provider requests and 6 results in the Astra provider call, fixed execution timeout, URL/provenance validation and finite retry budgets. Failed components cannot block unrelated tasks; policy-blocked and approval-gated tasks cannot be bulk resumed.
6. **Verified product delivery:** maintain pre-order manufacture and the private inbox. Public publication, prices, customer entitlements and payments only use their existing audited release/quality gates; no blanket authorization to publish low-evidence drafts.

## Owner and safety guardrails

- Do **not** turn 95 blocked tasks back into active tasks en masse. Read `factory_health` and distinguish absent independent sources, provenance/identity, policy, owner approval, and stale lease.
- Do **not** equate successful CI or staging migrations with live factory cutover.
- Avoid repeated paid API/token calls; local idempotency, digest deduplication, and useful evidence-triggered work are preferred.
- Preserve the existing websites, GitHub Actions → VPS → cPanel relay, host-key pinning, private database backups, and rollback.
- Do **not** claim scientific validation, real sales, regulatory compliance, or live store publication without independent evidence.

## Source-linked evidence

- GitHub Issue #41: https://github.com/mojtabarozegar11-ship-it/Saeit/issues/41
- Original package audit: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38574357158
- Disposable migration and durable-queue QA: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38576215113
- Independent manufacturing deployment: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38570825148
- Private delivery verification: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38571122351

**Current release gate:** Astra production replacement remains **NOT APPROVED BY TECHNICAL VERIFICATION** until the bounded research tick, regression safety, deployment-profile adaptation, and single-writer rollback procedure pass in an isolated copy.

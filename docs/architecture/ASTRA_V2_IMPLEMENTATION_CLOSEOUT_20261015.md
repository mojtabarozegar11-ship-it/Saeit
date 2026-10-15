# Astra Factory 2.0 — chained engineering closeout, 2026-10-15

## Plain-language executive status

**Technical engineering:** usable private research prototype + offline browser interface + auditable financial calculation core + independent test suite + versioned idempotent private manufacturing queue + CI artifact + on-VPS isolated canary.

**Commercial readiness:** NOT proven. No justified quality score of 90/100 or higher; score remains `null`. No buyer demand proof, no externally verified sales, no owner release approval, no authenticated storefront publication and no verified revenue.

**Continuous autonomous market-to-sale factory:** NOT yet operational. The prototype's durable queue can process new internally authorized briefs repeatedly when they exist, but it cannot autonomously verify customer buying intent, build arbitrary product types or guarantee a stream of distinct new goods. An idle queue is reported as NO_ELIGIBLE_WORK, never a newly produced product.

This work builds upon Astra's original durable DiscoverySnapshot/FactoryQueueItem pattern. It DOES NOT merge/overwrite code or migrate the existing live isolated factory database (live migration 0049 remains unverified). It avoids alteration of the three production websites and old VPS factory worker.

## What was actually implemented

1. **Market hypothesis selector**: `scripts/astra_opportunity_selector.py` — criteria-based offline review, source URL/hash/age filtering and hard eligibility gates. All source assertions remain provisional; no build or publication power.
2. **Existing research evidence adapter**: `scripts/astra_research_evidence_adapter.py` — read-only SQLite linkage from product/factory research project to ResearchSource/Evidence, and opt-in Astra snapshots only where schema exists.
3. **Live read-only research inventory**: [workflow 38652072237](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38652072237) found 257 ResearchProject, 479 ResearchSource, 479 Evidence, 477 Finding, 220 FactoryRun, 209 Product rows; 248 preliminary distinct source hostnames; no core_factoryqueueitem/core_discoverysnapshot. These DO NOT establish commercial demand.
4. **Competitor and method dossier**: `docs/research/ASTRA_V2_ORCHARD_INVESTMENT_MVP_DOSSIER_20261015.md` with IFAS, PSU, Alberta free competitor disclosures. Original mathematical implementation; no copying third-party tools.
5. **New distinctive reference software**: `product_prototypes/orchard_decision_audit/`, not identical to the two old fixed calculators. `decision_audit.py`: up to five options, 1–30 annual periods, year-0 spending, exact Decimal NPVs, relative alternatives, explicit price/yield/cost stresses, break-even revenue multipliers, yearly audit trace, real-vs-nominal and units restrictions, unverified-assumption warnings, negative-outcome reporting.
6. **Mobile-friendly offline local browser UI**: `index.html`, `style.css`, `app.js`, `serve_local.py` — editable annual ledger, scenario controls, source labels, input import/export, yearly trace, CSV export, browser print/save-PDF; API binds exclusively to 127.0.0.1, requires same origin, no external fonts/assets or persistent operator-data storage.
7. **Independent deliverable self-test**: `self_test.py` shipped inside ZIP along with fictional synthetic input. After extracting on any Python 3.8+ machine, `python3 self_test.py` checks first-principles NPV examples.
8. **Private manufacturing pipeline**: `scripts/astra_v2_private_pipeline.py` — exact allowlisted builder; persistent SQLite queue, single-writer file lock, private 0600 files, stable deterministic ZIP/source hash, independent tests before completing a build, SHA-stable manifests, no duplicate version counted on repeat, no paid API or store activation, truthful completed/empty/failed states.
9. **Independent GitHub workflows**: `.github/workflows/astra-v2-product-e2e.yml` — actual artifact ZIP + QA manifest available as short-retention Actions output with *synthetic code only*. `.github/workflows/astra-v2-vps-private-canary.yml` — bounded SSH pinned VPS isolated build + tests in private workspace without touching existing factory/sites. Retains only private prototype artifacts.
10. **Test paths**: `tests/test_astra_opportunity_selector.py`, `tests/test_astra_research_evidence_adapter.py`, `tests/test_astra_orchard_decision_audit.py`, `tests/test_astra_v2_private_pipeline.py`. Include synthetic evidence, strict gate/failure cases, financial corner cases, localhost cross-origin protections, actual distributable ZIP and self-test.

## Repeatable owner verification

GitHub runner has produced a synthetic-only product ZIP from actual source and verified QA gate:
- [Integrated artifact workflow](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/workflows/astra-v2-product-e2e.yml)
- [First passing VPS isolated canary](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38653716434)
- [Full CI](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/workflows/ci.yml)
- [Django CI](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/workflows/django-ci.yml)

Local independent demo (with repository source):
```bash
python3 scripts/astra_v2_private_pipeline.py demo
python3 -m unittest discover -s tests -p 'test_astra_v2_private_pipeline.py' -v
python3 product_prototypes/orchard_decision_audit/self_test.py
python3 product_prototypes/orchard_decision_audit/serve_local.py --port 8765
```
Open `http://127.0.0.1:8765/` on the machine running the local server. Example prices and yields are fictional.

The VPS canary's private paths are:
- `/home/githubops/factory-runtime/operations/astra-v2-vps-canary-source/` — only isolated prototype code.
- `/home/githubops/factory-runtime/private/astra-v2-canary-products/` — isolated queue, ZIPs and QA manifests.
Neither is the existing live Django database, the public site path, nor a new production loop.

## Objective status by release gate

| Gate | Observation | Result |
| --- | --- | --- |
| Architecture/legacy preservation | One original Master Agent; no blanket migration | Pass for branch-only implementation |
| Source/provenance inventory | 479 references, no verified buyer intent | Partial, not market proof |
| Opportunity ranking sandbox | Source and eligibility controls, 0 paid calls | Pass technically |
| New independent reference code | Offline software and web GUI built | Pass technically |
| Calculation accuracy | Synthetic known-value, stress, edge conditions | Pass automated tests; independent economist signoff missing |
| Application/browser security | Local bind, Origin/Host/CSP, input limits | Pass selected tests; external penetration review missing |
| Factory versioned build | Private ZIP, QA manifest, repeat-idempotence | Pass technical QA |
| Real VPS canary | Scoped private build and tests | Initial run passed; later source versions require matching run verification |
| Product market validation | No customer interviews or proven willingness to pay | **BLOCKED** |
| Production Stage 4→5 | Old factory DB lacks Astra queue migration 0049 | **NOT CUT OVER** |
| Continuous distinct commercial production | Needs qualified demand, builders, genuine pipeline tasks | **NOT PROVEN** |
| Commercial quality rating >=90 | Independent domain/user/release validation missing | **NOT ASSESSED** |
| Public publishing, payment, verified sales | Owner/store/legal gates absent | **NOT AUTHORIZED** |

## Prohibited shortcuts

- Never auto-activate products just because ZIP unit tests pass.
- Never insert fabricated customer reviews or make up market prices, demand, sales, discounts or a historical reference price.
- Never call 200 research hypotheses a proven catalog of products.
- Never convert a heartbeat tick, dossier re-scan or unchanged build into a new production KPI.
- Never use VPS canary success as permission to change live PostgreSQL/MySQL/cPanel databases, Django startup profiles or wallet/payment keys.
- Never present the existing two QA ZIPs as premium products without independent demonstration of value.

## Remaining external acceptance needed for commercial finality

1. Independently confirm *buyer problem and willingness to pay* and show a verifiable advantage over free competing tools; at least three actual domain-user walkthroughs (recommendation, not completed).
2. Have a qualified economist and real test operator validate input provenance, model omissions, economic assumptions, UI and documentation; correct issues and independently score each weighted quality dimension.
3. Prove repeatable production of **three genuinely distinct useful product versions across two validated builder categories**, not three ZIPs from one recipe.
4. Complete Astra schema code adaptation with existing Site/Master Agent policies, on a disposable copy first; pass migration 0049 and provider-sourced research→intake→build. Perform rollback-proven single-writer VPS cutover only under separately approved change control.
5. Complete a 24-hour private soak of correctly qualified work (not dummy jobs), bounded evidence sourcing and crash/lease recovery with measured costs.
6. Apply product-specific owner release/rights/price checks, destination publishing validation and real payment reconciliation. Never count an order as income until settlement and reconciliation.

**Current status:** Successfully engineered and technically tested **reference production pipeline**, not a certified sellable autonomous factory. Source remains in **draft PR #101**, not merged to live.

## 2026-10-15 verified operational addendum — private VPS heartbeat and crash recovery

This addendum supersedes prior statements within this document that a **private experimental queue scheduler** was not installed. The **old production factory** is still unchanged, and the newly installed private schedule is not equivalent to autonomous market research or commercial product manufacturing.

- Root issue fixed: an accidental double-escaped JSON newline caused the original VPS canary to fail on private brief enqueue. [Corrected VPS canary run 38655068663](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38655068663) succeeded: 23 finance tests, 18 integration tests; 2 distinct private reference version ZIPs were found at that point. Neither is a separate commercial product.
- Crash recovery added: under the exclusive lock the worker detects abandoned BUILDING rows and requeues up to 3 attempts; exhausted jobs are quarantined as FAILED_REVIEW without infinite loops. Three new regression scenarios exercise recovery, exhaustion and no duplicate new-product credit.
- [395 tests passed on both CI and Django CI](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38655208202) at the corresponding tested SHA, before the scheduler-only workflow and docs.
- [Private VPS scheduler preflight 38655355200](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38655355200) verified `githubops` cron support.
- [Private scheduler installation 38655465210](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38655465210) successfully installed exactly one scoped `*/5` cron row with flock and timeout after independently running 23 finance + 21 integration tests on VPS; immediate tick said `NO_ELIGIBLE_WORK`, no false claim of manufacturing. Backup stored in private directory, old factory schedule preserved and websites untouched.
- [Operations, observability, safe disable steps](ASTRA_V2_PRIVATE_SCHEDULER_OPERATIONS_20261015.md).

**Current goal completion:** 5-minute bounded *private queue processing* installed and initially checked; generation of genuinely new commercially qualified products, market-price evidence, independent score of >=90 and verified end-to-end store settlement remain unproven. Do not use private heartbeat, one repeated product family or successful CI as a sales KPI.

## 2026-10-15 additional verified implementation — SECOND INDEPENDENT PRODUCT AND LIVE PRIVATE INBOX

This section supersedes the former "only one specialized builder" and "no automated private intake" status. It does NOT lift the market/release quality gates.

### Delivered and tested

- **Specialist builder #2**: `farm_procurement_audit_v1` in `product_prototypes/farm_procurement_audit/`, distinct from the orchard long-term NPV tool. Normalizes usable agricultural input quantity for waste, delivery deadlines, supplier capacity and minimum orders; computes exact Decimal landed costs, explicit tax convention, discounts and adverse stress; produces a local printer-friendly HTML report and bundled self-check. Quote and supplier assertions remain operator-supplied, unverified.
- **Competition audit**: `docs/research/ASTRA_V2_FARM_PROCUREMENT_COMPETITION_AUDIT_20261015.md` compares with public university extension resources and existing free tools, explicitly warning that demand/paid differentiation is **NOT proven**.
- **Pluggable allowlisted registry** in `scripts/astra_v2_private_pipeline.py`: individual folder/file/test per specialist; refuses paid/unregistered builders and self-asserted market validation; existing orchid builder still supported.
- **Independent family/version counters**: distinct source hashes are not distinct saleable products; private QA reports have `quality_score=null` and false paid/store approval.
- **Bounded local inbox auto-intake**: each private five-minute tick scans `.../astra-v2-canary-products/incoming/*.json`, validates seven exact private-only fields, rejects malformed/paid/out-of-scope briefs, SHA-deduplicates and processes new allowed jobs. This is *supply-led without orders*, but it does not fabricate new eligible incoming briefs.

### Live VPS evidence / observations

- [Two genuinely distinct reference products on independently isolated VPS staging, run 38656383213](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38656383213): 17 procurement, 23 investment and 24 pipeline tests, two standalone ZIP self-tests and two distinct builder families. No public commercial product claimed.
- [418 CI tests passed, run 38656536247](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38656536247) and corresponding Django CI 38656536316 after the bounded inbox upgrade.
- [Private code upgrade through shared cron file lock, run 38656644371](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38656644371): staged/tests-run new two-builder code, retained old scoped-code backup and unchanged crontab, prepared one private procurement intake manifest, confirmed two private families. Follow-up safer rollback-enabled installation run 38656684527 also succeeded.
- [Read-only VPS health audit, run 38656970682](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38656970682) at UTC 2026-10-14 23:55:18: **1** private scheduler cron row, **2** families with accepted private QA, **3** distinct private ZIP content SHAs, **0** pending jobs, **0** failed-review jobs, **1** private inbox request file, **16 seconds** since latest private cron log update; active private code has 2 registered builder specialists. No evidence of public listing/paid sales.
- Live existing factory cron, cPanel, production websites, payment providers and financial ledgers were not modified by this scoped upgrade.

**Commercial result remains zero**: No independently confirmed buyer willingness-to-pay, no competitive user trial, no expert financial/procurement audit, no accepted 90/100 quality rating, no owner release authorization, no storefront/payment settlement. A 24-hour soak with monitored results is still NOT complete. Original Astra migration 0049 and Stage 4→5 market-provider cutover are NOT complete. Two families alone do not imply general autonomous content creation.

## 2026-10-15 latest technical update — verified 470 tests and bounded autonomous cache

The `feature/astra-factory-v2-architecture-20261014` branch now contains **three** distinct, privately QA'd source-builder families. [No-order three-product integrated artifact run 38659312298](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38659312298) produced and independently tested all three private ZIPs on a GitHub runner. [CI 38660936246](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38660936246) and [Django CI 38660936207](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38660936207) each passed **470** tests after further autonomous production hardening.

An unbounded case archive can fill a small VPS and halt unattended manufacturing. Accordingly, the order-free educator now has:
- 720 retained, byte-validated, synthetic-only ZIP slots, and at least 168 hours of protection for recent editions;
- fail-closed preservation of arbitrary user files, foreign ZIPs, tampered archives and symlinked objects;
- safe retirement only of exact original synthetic lesson content in oldest eligible hours when slots are full;
- the original 64 MiB private synthetic archive cap and 256 MiB free-space safety margin remain; lack of capacity stops production rather than modifying unrelated content;
- regression tests for retention, corruption, preservation of user/foreign files, long-window 48-edition no-order production and per-hour idempotence.

**Deployment truth check:** [read-only VPS audit run 38661021156](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38661021156), UTC 2026-10-15 00:36:51, observed **one** five-minute private cron marker, **two** builder families already producing private QA-accepted ZIPs, **one** autonomous educational edition, a cron-log age of **109 seconds**, and **third water/land builder NOT on VPS**. This check proves a current functioning periodic scheduler, NOT the branch's new rolling retention feature already running or a 24-hour uptime soak.

**Critical distinction:** The 720-edition retention change is currently **committed and CI-tested in GitHub, not independently verified as deployed to the VPS**. A remote cutover attempt for third builder + new runtime changes did not complete through the available controlled path; do not claim installation. The live original factory, website hosting and payment environment were not changed by these branch-only updates.

**Commercial qualification remains unchanged:** three original *technical prototypes*, not three independently validated saleable items; no verified buyer problem/willingness, no independent 90/100 score, no real publishing or revenue settlement. Third prototype competes with sophisticated existing academic tools (FAO literature, UC Davis and K-State tools, documented in `docs/research/ASTRA_V2_WATER_LAND_COMPETITION_AND_RESEARCH_20261015.md`). Do not describe rigorous mechanical QA as proof of a premium market.

## 2026-10-15 independent verification — THREE private specialist builders installed on VPS

This supersedes the earlier branch-only third-builder/deployment-pending observations above. It does **not** represent a commercial stage 4→5 cutover.

- Commit [91ac286](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/91ac28620930fd281392daf69727c476512c6990) extended the existing scoped `astra-v2-autonomous-no-order-vps.yml` workflow to deploy the third water/land specialist, run all independent third-builder tests on runner and VPS, and activate the private approved-source revision marker. A new per-operation source snapshot is created immediately before code cutover, replacing reuse of a potentially stale rollback archive. Rollback removes newly introduced third-builder source and source-autoplan marker only if they did not previously exist.
- [Actual private VPS deployment run 38662004142](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38662004142) **completed successfully**, reporting `ASTRA_AUTONOMOUS_BUILDER_FAMILIES=3`, `ASTRA_AUTONOMOUS_RETENTION_MAX=720`, and `ASTRA_AUTONOMOUS_EXISTING_CRON_UNCHANGED=true`. Third water/land product independently self-tested on runner and VPS. No public publishing or market validation.
- [Fresh independent read-only VPS audit run 38662206476](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38662206476) at 2026-10-15 00:49:35 UTC **passed**: exactly three accepted private QA families; third water builder present; one private five-minute cron marker; cron-log age 274 seconds; one educational case ZIP; bounded retention constants of 720 editions and 168 protected hours; no customer-order dependency; zero publicly listed products from this experimental pipeline.
- CI and Django CI each passed on the deployment commit: [CI 38662009870](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38662009870) and [Django CI 38662009877](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38662009877).

**Current operational truth:** The *isolated private Astra V2 experimental pipeline* now has three source builder families and a recurrent no-order synthetic educational case producer running on VPS. The existing **original** factory, hosted websites, payment processing, and commercial ledger were intentionally not deployed or modified by these workflow changes. A single successful cutover plus one fresh audit cannot establish 24-hour uninterrupted operation or perpetual creation of distinct, saleable products.

**Remaining blockers:** genuine external market discovery and buyer evidence, expert verification and user trials, cost/price/support/rights review, independent commercial quality scoring, old production factory schema 0049 + stage 4→5 architecture integration, 24-hour soak and actual reconciled store settlement. Keep PR draft until these are separately verified. Never count same-source rebuilds or synthetic lessons as sale-ready inventory.

## 2026-10-15 independent VPS artifact and release-gap proof

After the private three-builder deployment, a **separate read-only integrity gate** was implemented in scripts/astra_v2_release_gate.py, along with eleven independent synthetic regression tests and a GitHub-to-VPS audit action.

- [Release-gap gate run 38662963966](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38662963966): **SUCCESS**, 11 release-gate tests + 31 existing private manufacturing queue tests passing, plus actual SSH read-only live verification.
- Runtime verified **3 exact current specialist source revisions**, source contents matched corresponding ZIP payloads, ZIP SHA-256 matched QA manifests, technical flags stayed private-only, and a corresponding SQLite PRIVATE_QA_PASSED row existed for each artifact. The original queue was opened in SQLite read-only mode with query_only and was not modified.
- The audit explicitly reports **0 commercially qualified products**, no numeric commercial quality rating and no website, factory DB or payment mutations. Missing market/customer/expert/pricing/support evidence remains a hard release blocker; users or developers cannot simply set sale_ready=true in a manifest without making the technical check fail.
- [CI 38662971011](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38662971011) and [Django CI 38662970970](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38662970970) both passed for the release-gate workflow source commit.
- [New research validation workplan](../research/ASTRA_V2_MARKET_VALIDATION_EXPERIMENTS_20261015.md) cites existing UC Davis, Kansas State and Penn State tools and defines independent side-by-side economic, usability and buyer-value experiments. This is **competitor evidence, not buyer-demand evidence**.

**No automatic commerce cutover is justified by these findings**. Three technically verified prototype families are not three retail-approved products. The original Stage 4→5 schema migration, genuine evidence-backed opportunity intake, external domain validation, priced merchandising and real settlement verification remain separate unfinished tasks. Keep this PR in draft and never add invented quality scores or historical list prices for discounts.

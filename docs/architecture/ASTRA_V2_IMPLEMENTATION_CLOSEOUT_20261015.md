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

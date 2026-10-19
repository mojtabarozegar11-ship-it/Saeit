# Astra V2 — genuinely order-free private output stream

Updated 2026-10-15. The user explicitly requires factory operation **without requests, customer orders, demand events, or externally written work briefs**. This release implements an autonomous **educational case production lane**, not an imaginary always-profitable digital-product factory.

## What now runs without an order

The already installed private githubops VPS cron continues to run **every five minutes** and invokes `scripts/astra_v2_private_pipeline.py tick`. Its old inbox queue for *reviewed* product requests remains supported, but the new independent `scripts/astra_v2_self_directed_education.py` generates **one brand-new applied agricultural economics exercise for each eligible UTC hour** even with:

- no customer order;
- no site, shop or payment connection;
- no incoming manifest;
- no user prompt or ChatGPT session;
- no external API or LLM expense.

Internally the case producer rotates **four mathematical skills**: multi-year NPV, net-versus-gross input procurement, contribution/break-even, and constrained water-to-land allocation. A module includes a fictional scenario, 3 quantitative questions, independently computed key, labeled assumptions, machine-readable data and executable standalone self-test. All numeric farm examples are explicitly artificial; they are not invented claims about real farms, suppliers or current market prices.

## Counting truthfully

- **Autonomously generated educational edition**: a new, reproducible private case ZIP for a new hour, with a different set of economics parameters and answer key. Creation is hash-verified; repeats in the same hour are skipped. These are instructional units of the *same procedural curriculum*, not arbitrary new premium commercial product families.
- **Source-built reference products**: the orchard decision audit and farm procurement tool remain two independent specialist prototypes. Their QA status is separate from auto-generated educational cases.
- **Market-qualified / saleable products**: still **zero confirmed**. No independent buyer-intent interviews, expert endorsements, licenses, seller support or publicly authorized store listing.
- **Income**: not measured; do not claim automatic sales or revenue from a private scheduler.

## Safety and cost limits

- One automated edition per UTC hour, only while a private 64 MiB cap and 256 MiB free-space safety margin allow creation.
- Crash recovery uses the existing exclusive private queue lock; no double build for the same hour.
- Raw product cases/answer keys are held under `/home/githubops/factory-runtime/private/astra-v2-canary-products/autonomous_education/`, never inside Django cPanel docroot.
- If there is insufficient space, the builder reports `RESOURCE_REVIEW_REQUIRED` and stops making editions until resources are reviewed. Continuous *quality* cannot honestly be promised with finite resources.
- Existing original VPS factory, main branch, payment accounts, sites, old cron schedule and public store remain unchanged.
- The private hourly case producer must not be advertised as a proven high-value AI-generated product designer. It is a deterministic software/content generator, not a researched market-discovery or sales engine.

## Tests and independent evidence

- `tests/test_astra_v2_self_directed_education.py` includes deterministic math checks, four disciplines, genuine no-inbox/no-order production, ZIP and self-test, duplicate-hour prevention, resource limit, symlink rejection and consistency across restarts.
- The original two specialist QA suites continue to run independently.
- GitHub CI initially reported **438 passed** after the producer and tests were introduced, at commit `c5812707`: [run 38657949021](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38657949021), Django CI [run 38657948922](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38657948922).
- Dedicated VPS installation/workflow: [Astra V2 Autonomous No-Order Research Production VPS](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/workflows/astra-v2-autonomous-no-order-vps.yml). Its final success must be checked before claiming actual VPS execution. It performs a separate temporary staging test, acquires the shared private cron file lock, saves a rollback backup, updates ONLY this private R&D source and proves a case ZIP was created without an order.

## Future evolution to independent high-value products

To convert autonomous R&D editions into verified goods, add an independently verifiable online/offline discovery feed within legal data and privacy boundaries, a broader registry of proven specialist builders, independent expert evaluations, accurate pricing, support/rights review and an owner-authorized private-to-store handoff. No amount of repeated simulated cases by itself validates willingness to pay or justifies a 90/100 commercial quality score.

**Observed deliverable after this change:** an independent curriculum-product research stream, not a general AI business factory that can promise unlimited unique saleable products.

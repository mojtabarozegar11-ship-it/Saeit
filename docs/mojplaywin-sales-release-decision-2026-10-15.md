# MojPlayWin sales release decision — 2026-10-15

**Decision: NO-GO for public paid checkout.** The live website is reachable,
but live merchandise publication, secure paid settlement, and real transfer
fulfillment have not all been independently proven.

## Live checks on October 15 (GitHub Actions UTC 2026-10-14)

Read-only, pinned GitHub -> VPS -> cPanel relay:
- https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38653612702
- Active app: Django on MySQL; MojPlayWin passenger path is linked to staging.
- Shared core database: **190 product records**, **0 active**, **2 priced >0**,
  **0 orders**, **0 payment intents**. These are shared database totals, not
  independently labeled MojPlayWin-only revenue.
- **0 factory publication-permission records**.
- `mpw_commerce` is **not installed** in the live Django app; neither its
  migrations nor its actual invoice URL are deployed.
- All new commerce release gates are false.
- A privately stored existing digital book was detected, but file existence
  does not certify editorial/commercial quality or prove paid fulfillment.

Public endpoint probe:
- https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38654014177
- `/`: HTTP 200; `/store/`: HTTP 200; `/checkout/`: HTTP 404.
- HTTP 200 proves a page is reachable, not that purchase workflows function.

Chain connectivity:
- https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38652928293
- Read-only ETH and TRON public RPC and transfer indexer endpoints responded.
- No matching incoming transfers in the bounded 15-minute discovery window.
  This does not prove no transaction exists outside that window.
- **No real paid merchant-to-buyer fulfillment has been demonstrated**.

## Engineering work and scope

Draft PR #103: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/103

1. Additional fail-closed release/receipt tests, all 30 isolated SQLite tests
   passed: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38652431495 .
2. Disposable MySQL 8 integration of account signatures, ETH/TRX verification
   adapters, replay protection, ledger, and private downloads; product and core
   migrations fully applied in a disposable CI database. Investigated
   cross-backend test-infrastructure failures; only a final green full run
   counts as passing the MySQL release gate.
3. Runtime nonintrusive checks and a true Django URL resolver check; corrected
   a misleading earlier file-text heuristic.
4. **No live database changes, orders, crypto broadcasts, payment activations
   or production source changes.**

## Required sequential GO gates

All of these must be independently green before public activation:

- [ ] **Quality**: independently review every paid file for originality,
  completeness, usable length, seller rights, fair substantiated price, refund
  policy, support terms, non-broken access, and merchant publication permission.
  Do not claim a prior selling price without actual price-history evidence.
- [ ] **Schema**: full MySQL 8 E2E suite green on fresh disposable database;
  staging based on a restored privately held real production snapshot; abort on
  any unrelated migration, schema mismatch or transaction/locking error.
- [ ] **Wallets**: prove merchant control of receiving addresses using
  nonspending signed challenges; never place wallet private keys in GitHub.
- [ ] **Settlement**: verify an actual independently observed ETH/TRX mainnet
  transfer (small explicitly authorized amount, not a simulated hash) with
  correct amount, sender, recipient, finality, uniqueness and time window.
- [ ] **Delivery**: on a production-equivalent staging host, demonstrate
  signed customer checkout, invoice, confirmation, a single ledger entry,
  one private download grant, refusal for other users, replay protection,
  and recovery from provider/indexer failure.
- [ ] **Deployment safety**: precisely scoped live source diff and routing,
  full verifiable database/file backup, restore and rollback rehearsal,
  homepage/store/admin smoke tests, and explicit release approval.
- [ ] **Observability**: post-sale reporting showing actual live order,
  verified transfer, buyer entitlement, revenue and unresolved refunds;
  no simulated purchase counts as revenue.

Never bypass a red gate merely to activate a Buy button. Keep draft
pricing unpublished until the gates for that exact product are met.

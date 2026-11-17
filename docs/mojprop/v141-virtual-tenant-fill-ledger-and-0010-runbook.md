# MOJ-PROP-01 v1.4.1 — multi-tenant VIRTUAL fill execution and isolation

**Status:** Source-built, nonproduction, on Draft PR #2684. No customer order
matching service, no verified market quote/simulator publisher, no actual
customer enrollment, no applied *production* MariaDB 0009/0010 migration, no public
customer trade form, no broker execution or payments have been proven.

## Confirmed target design

- Numerous authenticated website traders each own separate virtual challenge
  accounts in the MOJ PROP WEBSITE. A client must never open, fund or enter
  an individual LiteFinance account, share the company's broker credentials,
  or deposit to the broker.
- The SITE backend is described by the owner as connected to ONE COMPANY
  LiteFinance account, but an independently authenticated, permitted,
  functioning broker adapter has not been verified by this PR.
- The 30 native TRX proposed challenge fee is a MERCHANT revenue event,
  not a broker deposit. Evaluation events are VIRTUAL and do NOT implicitly
  create broker orders. The single company broker book is a separate
  future aggregate-execution ledger, subject to actual risk/capital and
  authorization constraints.
- Legacy `prop_firm/allocation_service.py` still rejects using one broker
  reference as multiple funded accounts. Keep this guard: otherwise the
  company brokerage profit could be credited to many virtual challenges.

## Implemented code and purpose

| Module | Concrete implemented behavior | Boundaries |
|---|---|---|
| `prop_firm/plan1_v141_virtual_tenant_fill_ledger.py` | Pure per-trader, per-challenge XAUUSD open/close/partial-close replay, FIFO inventory cost, long/short P&L, exact 8-decimal money, 4-decimal source quote/quantity/fees, unique global source event IDs, contiguous challenge sequences, duplicate idempotence, temporal 28-day check, separate stage closed-position tallies and deterministic SHA256 per challenge | No market data authenticity, floating equity, stage pass, real orders or client authentication |
| `prop_firm/plan1_v141_virtual_tenant_models.py` | NEW isolated version-specific Django `PropV141VirtualBook` one-to-one to `PropV141SimState`, owner FK to actual site user; `PropV141VirtualFill` append-only intended rows with unique event ID globally, unique per-book sequence, quantity/price/fee check constraints | Existing v1.2 funded-account table unchanged |
| `prop_firm/migrations/0010_v141_virtual_tenant_books.py` | Creation-only migration dependent on `0009_v141_sim_replay_journal` and AUTH_USER_MODEL; defines book and fill schema and constraints | NOT applied to production; disposable MariaDB Django migrations, rollback and concurrency tested (13/13 PASS) |
| `prop_firm/plan1_v141_atomic_virtual_fill_service.py` | Server-internal signed event HMAC scoped to book, site owner and exact contract; `transaction.atomic` + row locks, full stored sequence reconstruction, hash and realized-P&L comparison, historical idempotence, globally exclusive event IDs, immutability after phase acceptance, fail-closed phase-two timing and terminal states | Not an HTTP endpoint; requires separately authorized upstream DEMO feed, protected signer keys and independently provisioned customer account |
| `core/mojprop_v141_private_portfolio_view.py` + `config/urls.py` | Tenant-scoped `GET /moj-prop-v141/portfolio/<slug:challenge_ref>/`, HTTPS + mojplaywin.com allowlist, logged-in owner only, no-store/noindex headers; shows purely realized virtual P&L and closed-position count with explicit non-funded / nonverified caveats | `MOJ_PROP_V141_PORTFOLIO_ENABLED` defaults FALSE (no setting set); NOT deployed, no trading POST, no real equity valuation |
| `prop_firm/plan1_v141_shared_company_master_review.py` | Separate mathematical single-company-account risk-capacity review for many website customers | All real order authority remains FALSE, no real MT5 adapter |

### Accounting interpretation

- Each `OPEN` adds an exact quantity/price lot with its own cost basis;
  each `CLOSE` consumes oldest open lots (**FIFO**) and records realized
  gross P&L only for consumed units. Every fee is debited once.
- A position counts once as **fully closed** only after ALL units close.
  Fifty fills or partial closes are NOT fifty unique fully closed positions.
- The stage-one and stage-two counts are separately returned for the
  **same** challenge. These are accounting candidates, not proofs of the
  50-position criterion, which remains under independent signed feed and
  full equity/session-calendar review.
- A website DEMO portfolio's `cash_balance_excluding_unrealized_usd` does
  NOT include floating mark-to-market, gap losses or margin state. It MUST
  NOT be labeled official equity, realized company broker profit, account
  funding, eligibility, settlement or payout.
- Canonical 4-place source decimals avoid a `1` versus `1.0000`
  hash mismatch after loading a Django DecimalField; quantities * price
  differences permit an 8-place exact USD P&L in proposed persistence.

## 2026-11-17 stage-clock correctness fix (stacked draft)

**Detected defect in #2684:** the virtual replay originally compared **both**
stages against the initial stage-one `opened_at_utc + 28 days`. This rejects
legitimate second-stage events after the original window despite the
two-consecutive-stage contract.

The isolated fix now reads the **persisted** stage-one acceptance timestamp
and stage-two start timestamp from `PropV141SimState` through the internal
writer. Stage-one fills must execute from the first start **up to and including** its recorded acceptance instant (but strictly before its own deadline). Stage-two fills must execute from the recorded second
start **up to but excluding** that stage's own 28-day deadline. A second stage
requires stage-one acceptance within the first deadline, followed by its own
recorded start; future or reversed transitions fail closed. Any still-open
stage-one inventory prevents second-stage review. No database schema change
is needed for this correction, since both transition fields already exist
in the independent `0009` state schema.

Regression checks: 16 additional pure replay tests and 2 new Django source
checks. These prove only the checked Python behavior and wiring; they do not
prove that production MariaDB transitions have been applied, that an upstream source is
genuine, or that the broker and payment service may operate.

**Deployment and commercial restrictions remain unchanged:** no merge to the
production branch, no `0009`/`0010` migration, no public orders, no TRX
settlement, and no automatic real-company broker execution.

## 2026-11-17 ephemeral MariaDB integration evidence

**EXACT SOURCE HEAD at verification:** `647e90cb77953065fe65180ce5eddd31ab0cfb47`.

- [Python source-unit CI #44155142665](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44155142665): completed **success** (835 source-unit cases).
- [Real Django/MariaDB CI #44155132828](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44155132828): **13/13 executed test cases passed**, 0 failures/errors, on a disposable MariaDB 11.8 Docker service. Actual Django migration `0001` through `0010` was applied to `test_mojprop_v141_ci_only` and the test DB was destroyed afterwards. Proved InnoDB/strict SQL, ownership isolation, HMAC rejection, a globally unique fill ID, one-to-one book state, positive-quantity DB check, atomic rollback, freeze after stage acceptance, and **two concurrent identical writes under row lock**.
- Isolated credentials were CI dummy-only; settings refuse non-GitHub operation, non-loopback host, unexpected schema and absent explicit ephemeral flags.
- **Not proven:** production/staging host disk capacity, existing old MariaDB schema collisions, off-host full backup and recovery, real market data provider, authenticated site HTTPS order form, legal enrollment, LiteFinance permissions, TRX settlement or any real trading. Disposable CI is a valuable runtime gate but **does not authorize a production migration**.

## Deployment and security NO-GO

**Do NOT enable `MOJ_PROP_V141_PORTFOLIO_ENABLED` or migrate 0010 on
production until ALL are independently demonstrated:**

1. Full consistent off-host production DB/app backup with a **successful
   isolated restore**, adequate disk capacity and verified schema
   separation from old v1.2 customer purchases.
2. Real authorized MariaDB/Django rehearsal of `0009` then `0010`,
   rollback, concurrent site users sharing unique event namespace,
   cross-tenant access denial, HMAC replay/rotation, state transitions
   and row locks. Source tests only compile/inspect ORM; they are not
   a substitute for this rehearsal.
3. Independently authenticated upstream virtual price/fill/equity data,
   end-to-end quote timestamps, signed complete raw event archive outside
   the live DB, and customer-visible statements derived from verified data.
4. Legal eligibility/terms/refund/KYC review for paid challenge evaluation,
   lawful financial promotional-post condition and approved 30-native-TRX
   server-side settlement before creating any PAID customer.
5. Independent proof of LiteFinance site-to-company-account connectivity
   and broker permission to route orders originating from multiple
   users into one company account. The VIRTUAL engine does not require
   or perform that brokerage action.
6. Owner-authorized production rollout with security controls, explicit
   flags, tested restore and monitoring. Any current live files remain
   untouched and must not be silently overwritten.

**Release flags remain FALSE. No broker order, fee, TRX transfer, email,
enrollment, DB migration, production deployment or payout is performed.**

### Regression evidence
Exact passing CI runs must be tied to their source commit SHA:
- [754 verified Python source unit tests](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44148489647)
- [797 verified after isolated Django model/migration/internal service changes](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44149821309)
- Current [835/835 source-unit CI](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44155142665) plus [13/13 ephemeral MariaDB integration CI](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44155132828) passed at exact SHA `647e90cb77953065fe65180ce5eddd31ab0cfb47`; neither validates production readiness.

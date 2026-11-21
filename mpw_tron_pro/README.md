# MojPlayWin Pay — Native TRX Checkout (isolated v0.1)

**Status: staged source, NOT deployed; no live checkout integration, no actual wallet or money testing.**

This module provides a TRON-only non-custodial payment checkout starter: responsive accessible buyer UI, customer invoice receipts, price quote rounded to integer Sun, unique per-invoice destination allocation (merchant-controlled public address pool), server verification via TRON Solidity-node finalized transaction body **and** receipt, atomic payment ledger and replay protection. It contains **no merchant private keys and no withdrawal functionality**.

## Visual review

From repository root run `python -m mpw_tron_pro --preview 8765` and open `http://127.0.0.1:8765`. Preview contains **NO real receiving address**, and all payment controls are disabled.

## Local isolated tests

`python -m unittest discover -s tests -p 'test_mpw_tron_pro.py' -v`

Tests run without TRON funds, API secrets or external requests. If the browser preview is desired, it uses only Python standard library. A real invoice QR uses optional `qrcode>=8,<9` (`pip install 'qrcode>=8,<9'`); otherwise the address-copy fallback is shown. QR encodes **the receiving address only**, since amount-bearing wallet links are not universally supported.

## Controlled operational design (NOT enabled)

1. The owner pre-generates many TRON addresses **offline** in a wallet/cold custody tool, retaining private keys offline. Only **public address strings** are registered through `InvoiceLedger.add_public_address()`. A destination is reserved exactly once and never recycled. **Funds arriving at those addresses will not be automatically swept**; the owner must retain access to every address and use a separately security-reviewed, compliant wallet procedure for consolidation. Do not add inaccessible addresses.
2. Integration uses a **trusted merchant-backend** to POST `{ "order_id": "...", "product_title": "...", "usd": "4.00" }` to `/api/merchant/invoices` with header `Authorization: Bearer $MPW_TRON_MERCHANT_KEY` (random 32+ characters). This secret must **never** appear in browser JavaScript or public GitHub. A live CoinGecko USD/TRX rate is checked server-side; failures disable issuing new invoices.
3. The merchant's app shows the returned unique `checkout_url`. Only the bearer holding that high-entropy private URL can see the invoice or submit a txID. HTTPS-only, no third-party assets, no-referrer, restrictive CSP. Protect logs and backups containing private checkout URLs.
4. A payer sends the *exact* amount of **native TRX** on **TRON mainnet** to the invoice's unique receiving address. Public chain proof must match txID, amount, destination, type, and time window and appear in **solidified** body and receipt. Unique txid and address constraints prevent cross-order double attribution. Payment success only writes `paid`; **no goods are released by this standalone module**.
5. Production must integrate with the **actual live commerce source**, order-authentication/fulfillment/receipt pipeline and durable job scheduler. Add robust periodic reconciliation so status can update without txid paste, accounting for TronGrid quotas, pagination, deep chain sync, node outage and ledger recovery. The current implementation has an explicit user-submitted txID verifier plus status polling; a bounded `reconcile_pending` address-history scanner is implemented but **not scheduled or tested on live chain**, and needs a durable cursor, retry/backoff and operations checks.
6. This module is intentionally not imported by `config/settings.py` or mounted in `config/urls.py`, and does not replace existing payment URLs. No production mutations should happen on main branch merely by merging the isolated code. A separate approval-gated release with cPanel backups, test purchase and rollback evidence is required.

## Exclusions and blockers

- **Not a public payment processor or bank**: no Visa/Mastercard, no custody, no customer card acceptance, no automatic merchant payout, no compliance bypass.
- Native **TRX only** in v0.1 (TRC-20 transfer requires a distinct ABI/event-validated verifier).
- A unique address per invoice ensures payer-to-order attribution even if a public transaction hash is copied by someone else. It **requires an operational address pool under documented owner control**; using a shared Trust Wallet receiving address would invalidate this security property.
- **TLS trust**: `TronGatewayApp` requires `wsgi.url_scheme='https'`. Reverse proxies must not trust client-supplied `X-Forwarded-Proto`; the hosting server must set the scheme from its authenticated TLS edge. `public_url` is pinned to `https://mojplaywin.com` or `www`. Never host this WSGI app directly via development server for real money.
- **Scale**: current SQLite ledger is a one-process pilot. Production requires PostgreSQL, migrations, durable multiworker locking, reconciliation/error ledger and monitoring before money is handled.
- Fraud/ops: handle expired invoices and over/under-payments via manual review/refunds with owner authorization and a separate procedure; the verifier intentionally rejects any not-exact amount.
- The module currently uses one TRON RPC provider. Production must add provider health, stale node alerts, conservative node failure behavior and optionally independent cross-validation.
- USD/TRX price feed is public CoinGecko without a rate SLA; quote policy needs operational price freshness/availability limits.
- Account-specific merchant, country eligibility, risk compliance and fiscal rules need independent review for commercial operations. No representation of being a regulated processor.

## Source of truth

TRON finalized proof: https://developers.tron.network/docs/api-signature-and-broadcast-flow and https://developers.tron.network/reference/transactions-1 . The buyer UI is an original MojPlayWin design, not a copy of another site's interface.


## v0.2 visual redesign (2026-10-21)

- Redesigned payment presentation in `static/checkout.html` and `static/checkout.css`:
  light premium fintech palette, prominent exact TRX quote, clear TRON network and address,
  desktop order summary, phone-first viewport, expanded status and accessible fallback transaction check.
- Replaced copy labels using nested text targets without changing the copy operation.
- Paid/expired status now updates visible status panel instead of only a small feedback line.
- The design preview must never show a live address or permit funds. No production routing changed.
- Browser checked at 390px mobile and 1440px desktop without horizontal overflow, using
  the preview-only HTML and no wallet or RPC access.
- Local `python -m unittest discover -s tests -p 'test_mpw_tron*.py' -q`: 41 tests passing.
- `tests/test_mpw_tron_checkout_ui_v02.py` adds 8 contract tests for safe preview,
  existing IDs, quoting fields, viewports, status transitions and XSS escaping.

**Still blocked:** merchant-controlled receive-address pool, safe DB migration,
production site integration with authentic cPanel source, real finality + delivery
E2E, security review and owner-approved deployment. **Do not merge as production-ready.**

## v0.3 — wallet-first checkout and safer settlement (2026-10-21)

**Staged development milestone, not a live payment system.** This version adds substantive payment capabilities, not a paint-only redesign:

1. **Trust Wallet payment handoff.** The official documented deep link `https://link.trustwallet.com/send?asset=c195&address=<verified TRON address>&amount=<exact TRX>` is produced on the trusted server from the **integer Sun** invoice quote. The native TRX asset is `c195`. The wallet still asks the payer to review and approve; this is **not** a payment-success signal. The link is absent if invoice is expired, paid, or preview-only. No private key or seed is needed.
2. **TronLink direct wallet path.** Optional browser integration using the modern injected `window.tron` provider. Explicit authorization (`eth_requestAccounts`), strict mainnet chain ID (`eth_chainId = 0x2b6653dc`), inspection of the unsigned `TransferContract` destination/sender/Sun amount before signing, signature in the wallet, and broadcast once with manual customer confirmation. Broadcast success is **not** chain finality. Users without an injected supported wallet fall back to Trust Wallet or QR. No third-party JavaScript is loaded on the checkout page.
3. **Automatic incoming transfer discovery:** `reconcile_pending()` now records *finalized* underpayments/overpayments for manual review rather than ignoring them. It never aggregates partials or silently credits a mismatched amount. `worker.py --once` provides a bounded, operator-controlled scan with an exclusive file lock and audit counters. The scan process is **not installed or scheduled** on the production server.
4. **Detect real worker health:** the ledger stores per-run health counters and reports `not_configured`, `running`, `degraded`, or `stale`. Buyer pages no longer pretend background monitoring is live when no worker has run.
5. **Verified merchant reconciliation endpoint:** merchant-authenticated `GET /api/merchant/orders/<order_id>` returns an immutable verified payment state, transaction hash and block details (only if paid), and a `fulfillment: not_integrated` marker. **No digital product gets unlocked in this isolated prototype.**
6. **Bounded manual verification:** at most four verifier calls per invoice per minute and 24 per hour, with `429 Retry-After` instead of unlimited costly TRON RPC calls. Idempotent paid rechecks need no RPC; different transaction IDs on an already-paid invoice are rejected. New transfers are disabled when a quote is expired, already paid, or under/overpaid, while an earlier pending transfer remains reviewable.
7. **Status transparency:** buyer sees quote → on-chain submission → finalized stages, under/overpayment review, browser recovery on returning to private checkout URL, receipt link only after verified finality, and a running/degraded scanner message. Status refresh is automatic in the browser, but detecting incoming transactions **depends on a separately scheduled worker**.

### Operator-only API contract (illustrative; NOT provisioned on VPS)

- `POST /api/merchant/invoices` with `Authorization: Bearer <backend-only key>`; trusted storefront must source its USD product price from its own database and retain the returned checkout URL; **do not** expose this key to browser scripts.
- `GET /api/merchant/orders/<order_id>` with the same key; the store may display a paid receipt **only** after backend verification. Independently authorize product ownership, never trust a browser status flag.
- `GET /api/status/<opaque capability>` for buyer status (private high-entropy checkout link; redact token from logs, analytics and referrers).
- `POST /api/verify/<opaque capability>` for user-supplied transaction hash, same-origin and bounded; no user confirmation alone can produce a paid record.
- Offline merchant-owned receiving addresses must be supplied as **public strings only**. **The current merchant wallet alone does not create an inventory of unique deposit addresses.** Never generate/record addresses for which the owner has no key custody. There is **no automatic sweep/withdrawal feature**.
- Worker example, *only on an owner-audited private Linux directory with 0700 permissions, and only after live app integration and approvals*: `MPW_TRON_DB=/secure/gateway.sqlite3 MPW_TRON_LOCK=/secure/scan.lock MPW_TRON_API_KEY=<from-private-env> python -m mpw_tron_pro.worker --once`. Do not put keys in shell history or public repositories. This command executes one bounded scan; **it does not install a cron job**.

### Testing evidence

- `python -m unittest discover -s tests -p 'test_mpw_tron*.py' -q` — **63 local unit/mock tests pass** (TRON transfers simulated; zero funds spent).
- `python tools/browser_qa.py` — Chromium UI check at 390px and 1440px, wallet authorization/send via a **mock injected provider**, and rejection of wrong chain before any signature or broadcast. No real wallet connection or chain interaction occurs.
- **Not yet proved**: installed Trust Wallet's precise deep-link UX on target devices, genuine TronLink integration across versions, real TRX mainnet deposit settlement, refund/chargeback controls, actual VPS/Passenger ingress, shopper-session/order/fulfillment integration, accessibility audit, external security review, rate quote SLA, RPC health/failover, production PostgreSQL migrations, and monitoring under load.

**Do not merge, enable, present as a real payment processor, or publish public wallet addresses until these gates are satisfied.** Never use a prior GitHub/cPanel status log as proof of an actual completed payment.

References: [Trust Wallet deep linking](https://developer.trustwallet.com/developer/develop-for-trust/deeplinking); [TRON DApp integration](https://developers.tron.network/docs/tronlink-integration); [TRON confirmation semantics](https://developers.tron.network/docs/confirmation-semantics); [TRON network chain ID](https://developers.tron.network/reference/eth_chainid).

## v0.4 — autonomous payment-to-product delivery pipeline (21 October 2026)

**STAGED / NOT LIVE.** Improvements focus on the automation engine, not another design skin.

### New verified lifecycle

1. Store creates a merchant-authenticated invoice; merchant-only TRON receiving addresses are reserved atomically. Buyer can leave checkout after approving a wallet transfer. There is no requirement to paste a transaction ID when the monitoring worker is running.
2. Background `reconcile_pending` checks bounded address histories, takes only successful solidified mainnet native-TRX transfer proofs, and marks one invoice PAID exactly once. The scanner has **per-invoice durable due-times** and bounded exponential backoff so a stuck old order does not indefinitely starve new orders. Invalid RPC responses never promote a payment.
3. In the **same SQL transaction** as payment settlement, the engine inserts one immutable `delivery_outbox` event (a `mpwtr_*` event ID stable across retries). If the SQL commit fails, neither payment nor delivery event succeeds.
4. The same worker run (with single-instance filesystem lock) attempts outbound **server-to-server, HMAC-SHA256-signed** fulfillment to the **pinned** HTTPS endpoint `/api/payments/tron/fulfill/` on `mojplaywin.com`. It sends no wallet keys and never transfers crypto itself.
5. The store must verify the exact signature, check the real customer order and product in its own DB, and atomically grant **one** unique entitlement for the `event_id`/`order_id`. Only a verified JSON receipt containing exactly the same event/order, plus `status=delivered` and a durable `delivery_id`, is accepted. An HTTP 200 alone is not enough.
6. A timeout, missing reply, crashed worker or lost acknowledgement leaves the same event in a **retryable queue**. Exclusive durable claims have a 120-second lease and bounded exponential retry delay. Every retry uses the **same event ID**, requiring the merchant to implement idempotent fulfillment. The buyer sees distinct payment and delivery states; never a fictitious download link.

### Before connecting commercial customers

- The live `mpw_commerce` code on cPanel (not mirrored in this Git repository) MUST implement and independently test the real store-side fulfillment endpoint. `store_receiver_contract.py` validates signed input but DOES NOT create product entitlements; the real Django handler must use its own order/ownership/stock checks with `transaction.atomic()` and a unique constraint. Do not install this router in live checkout until audit and backups.
- **A single Trust Wallet address is NOT a pool of one-time receiver addresses.** Dedicated-address invoice allocation currently remains mandatory. No deterministic address generation was enabled without confirmed user key custody. This is a remaining operational blocker, not something solved by CSS or HMAC.
- PostgreSQL conversion, one-time schema migrations, key rotation, high-throughput concurrency, crawler pagination/RPC rate ceilings, staged product fulfillment, observability and human exception review remain release gates. SQLite here is pilot-only.
- TRON mainnet settlement/refund and real mobile wallet acceptance must pass independent live tests before the owner authorizes production routing. No real transfer or product release has been claimed in v0.4.

### Autopilot operator contract (OFF by default)

A trusted and audited scheduler on the private VPS may run **one bounded, locked cycle** through:

```bash
python -m mpw_tron_pro.worker --once
```

Required **server-only environment** (set using a secret manager, not shell history):

- `MPW_TRON_DB` — protected, initialized local pilot database (production replacement: PostgreSQL)
- `MPW_TRON_LOCK` — lock file path alongside the private DB (folder mode `0700`)
- `MPW_TRON_API_KEY` — optional mainnet indexer/RPC key (provider terms/rate limits apply)
- `MPW_STORE_DELIVERY_ENDPOINT` — exact trusted `https://mojplaywin.com/api/payments/tron/fulfill/`
- `MPW_STORE_WEBHOOK_SECRET` — strong separate shared secret also configured in the actual store; never exposed to browser or git

**NOT scheduled**: one-minute VPS cron with a lease/lock, alerts, TLS/SSH access, monitoring and auto-restart are not provisioned. Running this command now would not magically enable a live checkout. Do not schedule from GitHub Actions or send credentials to CI.

### Evidence

`python -m unittest discover -s tests -p 'test_mpw_tron*.py' -q` — 93 isolated tests succeeded; no external funds.

`python tools/browser_qa.py` — Chromium 390px + 1440px previews, one simulated wallet send, rejected wrong-chain, and simulated paid+delivered status (no real wallet or TRON network). The full synthetic event pipeline test covers **detected transfer → solidified proof → paid order + atomic outbox → signed store validation → idempotent entitlement acknowledgement**, with mock chain data and a mock merchant handler. This is engineering evidence, not a successful live sale.

### Security boundaries

Receiver handler rejects invalid HMAC, JSON duplicate keys, wrong network and changed amounts. Outbound delivery refuses HTTP, foreign domains, query-string redirect targets and nonstandard endpoints; redirects are explicitly disabled. No mnemonic, private key, hot signing or withdrawal route. Incoming non-exact payments remain manual-review and cannot auto-unlock products.
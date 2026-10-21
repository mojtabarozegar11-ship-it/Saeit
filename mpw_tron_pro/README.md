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
5. Production must integrate with the **actual live commerce source**, order-authentication/fulfillment/receipt pipeline and durable job scheduler. Add robust periodic block-based address discovery so status can update without txid paste, accounting for TronGrid API quotas, pagination, deep chain sync, node outage and reconciliation. The current implementation has an explicit user-submitted txID verifier plus status polling; **automatic inbound address discovery is not yet implemented**.
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
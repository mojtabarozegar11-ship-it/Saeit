# MOJ Commerce v0.4 — source-only multi-merchant checkout and reconciliation

## Scope implemented (NO MONEY, NO DEPLOYMENT)

- One buyer, one ZIP product, one mainnet native TRX invoice. Logged-in buyer must use authenticated, CSRF-protected POST. An idempotency key binds the buyer/merchant/product to exactly one immutable order reference. Client must not supply amount, rate, or wallet address.
- Server quote comes only from an operator-injected callable, has controlled bounds and rounds up to integer Sun; the default is not configured, so invoicing fails closed.
- Seller must be **approved**. Each receiving address must have a unique, previously unused Base58Check TRON address with a verified `signMessageV2` proof belonging to **that seller**, never a shared global account. Address selection is guarded by PostgreSQL row locks and database uniqueness; one-time-use addresses are never silently recycled after expiry.
- Purchase and scan state live in the same Django database, not in the older global SQLite invoice database. A buyer can query only their own order status; a pending expired/suspended order will not advertise an active payment address.
- Optional server-side, bounded scanner uses the existing TRON indexed incoming-tx discovery **only to find candidate txids**. It checks actual solidified native TRX body + receipt, exact amount and recipient, produces a deterministic signed fulfillment event, then calls the existing Django entitlement issuance with a **second independent body-and-receipt read**. Same provider, two distinct queries; this is **not** cross-provider quorum.
- Under/overpay to a known seller-owned address is logged with unique txid for manual review; there is no automatic credit or refund for incorrect values.
- Five-minute buyer-bound download links and delivery receipts are inherited from v0.3.
- Bounded scans maintain `PurchaseScanState` in PostgreSQL. Scanner and checkout are **OFF by default**. The management command refuses SQLite. No cron or deployment is installed.

## API and operator contract

`POST /moj-commerce/merchants/<merchant-uuid>/products/<int:product-id>/checkout/`
`Content-Type: application/json` and CSRF authenticated browser session:

```json
{"idempotency_key":"unique-32-url-safe-characters-xxxxx"}
```

Response contains exact integer Sun, owner-controlled receiving address, order reference, ten-minute expiry and a buyer-only status route. Never take wallet recipient or conversion quote from browser fields.

`GET /moj-commerce/orders/<reference>/status/` only for authenticated owner of the order.

Required config settings (not provided in live cPanel):

- `MOJ_COMMERCE_CHECKOUT_ENABLED=True` **only after operator approves real seller wallet/address verification, secure pricing, ZIP availability, access, backup and test purchases**.
- `MOJ_COMMERCE_TRX_RATE_PROVIDER` callable (trusted server-side, fresh bounded rate; do not use a buyer rate).
- `MOJ_COMMERCE_REQUIRE_FILE_PRESENT=True`; private uploaded ZIP requires independent malware/rights checks.
- `MOJ_COMMERCE_SCANNER_ENABLED=True` only for approved PostgreSQL maintenance execution; `MOJ_COMMERCE_FINALIZED_TRON_CHECKER` must be independent finalized-body/receipt verification and `MOJ_COMMERCE_FULFILL_SECRET` private.
- `python manage.py moj_commerce_scan_once` is source only; cron and secrets intentionally not configured.

## Verified vs blocked

New test cases cover seller isolation, empty address pool, stale-replay invoices, buyer authorization, malformed requests, quote failure, proof restrictions, incomplete Solidity receipt, wrong amount, and actual in-process buyer-to-file flow using **MOCK blockchain records**. Separate PostgreSQL CI tests exercise two simultaneous buyers competing for one address and same-key replay; no SQLite claim of financial concurrency.

**Do NOT merge, enable routes, or accept money until**:
1. Actual live cPanel `mpw_commerce` code and order DB are inspected with owner permission. There is no verified mapping from its live order IDs to these source-only routes.
2. Proof-of-control from merchant's real installed Trust Wallet/TronLink; legal seller identity / wallet ownership / sanction eligibility approved.
3. Real, independently-operated second TRON RPC provider, meaningful provider resilience, rate limits and scanner lag alerting.
4. Real PostgreSQL migration/backup/rollback evidence, locked secret storage, private malware-scanned files and recovery drills.
5. E2E live mainnet low-value seller-approved payment and **buyer ZIP receipt/download** under explicit owner authorization.
6. Different merchant production tenants can neither see invoices nor receive one another's funds; no expired invoice enables a payment request.

Known pilot limitation: product price/file metadata are mutable in the current schema. `finalize_signed_purchase` deliberately rejects a product-price change or asset deactivation, favoring safety over accidental delivery; introduce immutable approved product revisions before commercial launch. One-time receive-address allocation has finite inventory, must be replenished via verified public addresses. No USDT, MOJ1, withdrawals, card payments or wallet custody.
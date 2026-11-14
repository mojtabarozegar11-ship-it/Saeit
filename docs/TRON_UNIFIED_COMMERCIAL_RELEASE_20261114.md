# Unified native-TRX merchant gateway — FA Zomorod Melal / EN MojPlayWin

Release work: 2026-11-14. STATUS: **branch implementation only, not deployed or paid-canary verified.**

## Owner wallet, supported currency and proof

Recipient: THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73 (owner-supplied Trust Wallet screenshot; Base58Check verified). Mainnet network: TRON. Only native TRX supported; **not** USDT/TRC20/other networks. The merchant server does not hold keys, sign or broadcast transfers. Senders pay their own network charges. Do not transfer any money to launch this code.

Receipt requires a single native TransferContract and *identical solidified* transaction body and receipt from PublicNode and TronGrid: matching txID, recipient, exact SUN amount, block metadata, invoice window, sender and success status. A QR code, buyer claim, HTTP 200 or event from one indexer cannot settle an order.

## Implementation and routes

- core/tron_gateway_verify.py: dual solidified RPC proof; no broadcasts.
- core/tron_gateway_invoice.py + core/migrations/0041_trongatewayinvoice.py: dedicated persistent invoice, unique never-reused TRX amount for one wallet, buyer email and site, claim hash, verification digest and txid.
- core/tron_gateway_web.py: CSRF/HTTPS/host checks, email-only guest account with unusable password, email ownership proof, active catalog quote, original core Order/OrderItem/PaymentIntent and atomic ledger/event settlement, recovery.
- core/tron_gateway_delivery.py: paid-only, email-owned private digital fulfillment; no symlink path traversal; file SHA256 must match rights-approved catalog hash.
- templates/core/tron_gateway.html: RTL Persian and English self-service checkout.
- core/management/commands/tron_reconcile.py: independently retries submitted TXIDs after RPC outage from a server cron.
- tests/test_unified_tron_gateway_verify.py: deterministic proof and failure-path tests.

The same Django app exposes /pay/tron/product/ID/, /pay/tron/invoice/ID/, /pay/tron/recover/ and /pay/tron/download/ID/ on explicitly authorized hosts. **A separate site or subdomain on another application server is NOT magically integrated by these URLs.** Each real host must route to this app or use an independently audited integration with the merchant ledger.

## Product admission

An eligible active Product has verified catalog rights and fulfillment metadata: rights_cleared, publication_approved, sales_enabled, in_stock and fulfillment_ready all exactly True. fulfillment_type must be digital, service or physical. Digital assets additionally require valid rights_document_sha256, sha256, matching rights_asset_sha256, and an asset_relpath inside the configured private directory with bytes matching sha256.

Product.metadata must contain an operator-approved integer tron_price_sun, tron_price_currency equal to Product.currency, and tron_price_reference_amount equal to str(Product.price). The module does **not** fabricate conversion rates. Approved pricing provenance must be recorded by merchant staff. The Persian site must distinguish TOMAN/IRT (تومان) from IRR (ریال) and must NOT relabel an IRR database value as تومان without an audited 10:1 conversion. English catalog checkout requires USD.

An irreversible unique-amount adjustment of 1–10,000 SUN (maximum 0.01 TRX) distinguishes invoices and is disclosed in the actual checkout. This fixed micro-adjustment pool is finite: on exhaustion the system fails closed, rather than reusing an earlier payment amount. A scalable deposit identification scheme should be designed before very high transaction volume.

## Strict go-live checklist (cPanel, no blind deployment)

1. Compare the *effective* MojPlayWin staging source (/home/zomorod2/Saeit-staging and Passenger WSGI) with this public Saeit branch and the private MojPlayWin-Gateway-Private snapshot. Preserve prior guest orders, paid entitlements, existing active reconciler and database changes. The private snapshot is NOT a full deployable application.
2. Back up source and database privately. Resolve any drift and migration numbering conflicts with the real production source. Run python manage.py showmigrations core; python manage.py migrate --plan; python manage.py makemigrations --check --dry-run; python manage.py check --deploy and the new unit tests. Apply only the reviewed core migration once.
3. Configure real HTTPS, Django ALLOWED_HOSTS, CSRF trusted origins and trusted proxy SSL settings for each *real* subsite; never trust arbitrary Host or X-Forwarded-Host headers.
4. Configure an operating SMTP sender; an independently verified multi-worker shared rate-limiting cache such as Redis/Memcached; private digital storage outside the webroot, read permissions and file checksums.
5. Set private settings: TRON_UNIFIED_RECEIVER to the exact address above; TRON_UNIFIED_ALLOWED_HOSTS to an explicit list of real FA/EN domains and subsites; TRON_UNIFIED_PRIVATE_DIGITAL_ROOT to an absolute private directory; TRON_UNIFIED_SHARED_RATE_LIMIT_READY=True only after confirming shared-cache behavior. Set TRON_UNIFIED_PUBLIC_ENABLED=True only after owner-authorized paid mainnet acceptance. Do not commit private settings or credentials to GitHub.
6. Run a server-owned cron every minute in the correct virtualenv: python manage.py tron_reconcile --limit 100. Never depend on GitHub Actions for payment reconciliation.
7. Publish links from each site/storefront only for independently approved, deliverable catalog items. Perform an expressly authorized low-value *real* TRX payment; verify receipt, idempotency, email recovery, downloaded asset, refunds and unpaid/other-buyer denial before opening public sales.
8. Verify domain-by-domain that DNS, TLS, backend and payment gateway actually respond. A GitHub green check or HTTP 200 alone is NOT proof of commercial operation. Document local tax, consumer and cross-border virtual-asset compliance per market.

**No cPanel deployment, database migration, SMTP email, wallet transfer, cron installation or spending has been executed by this branch.**

## Known boundaries

- Buyer must verify email and submit the actual transaction hash; automatic receiver-wide blockchain discovery is not yet implemented. The scheduled command retries candidate hashes, not scans all deposits. Out-of-band and late transfers need a merchant review/refund workflow.
- A paid digital file is protected by proof+ownership+rights hash. A physical/service paid order needs separate execution and delivery evidence.
- The new provider does NOT migrate or replace existing MojPlayWin walletless payment intents; old pending orders must remain accessible.
- The mainnet round-trip remains unproven until actual owner-approved payment and confirmation. Do not claim live revenue or 100% readiness on code existence alone.

## Cycle 2 — 2026-11-14 — commercial hardening

The source branch adds independent solidified-node evidence parsing, redirect denial, valid HTTP JSON-only responses, and strict native TransferContract validation. Indexer or browser metadata are only candidate evidence, never settlement. Every mainnet settlement must have an identical finalized body and receipt from TWO different operators.

The invoice now preserves the approved private digital file path, rights document digest and original SHA256. Repricing or delisting after a paid order does not revoke the original digital entitlement; an explicit rights_revoked=True or delivery_suspended=True flag still prevents a disputed delivery.

Every approved TRX price requires a dated tron_quote_valid_until_ms timestamp, set no more than 24 hours in advance. No invented Toman-to-TRX FX rate is provided. Production quote provenance, taxes, margin and refund policies must be approved in the seller's private records.

The email confirmation rotates the Django session key, proves the exact host and expires the authorized email session after 15 minutes. Email recovery can authorize existing unexpired invoices. SMTP failure or zero accepted messages is never called a successful invoice.

Public merchant endpoints require real, shared atomic Redis/Memcached throttle, not per-worker LocMemCache, and enforce independent per-email, per-IP and per-pair rate controls. Redis Python client is a no-cost software dependency, NOT a deployed Redis service.

Fair reconciliation persists per-invoice attempt timestamps to prevent a few old unresolved payments starving newer customers.

### Optional automatic incoming TRX discovery

Django worker command: python manage.py tron_discover --pages 3 --max-checks 12

This uses TronGrid's confirmed receiver-specific account history to propose transaction hashes. It uses bounded pagination and a configured private TRON_UNIFIED_TRONGRID_API_KEY. It credits ONLY after the independently pinned dual-solidity proof matches the exact invoice wallet, SUN amount, inclusion timestamp and recipient. An insufficient public API quota or provider failure leaves the invoice pending; no transfer is broadcast. Never infer completeness when pagination is truncated.

Fallback manual-hash reconciliation must remain enabled on the actual merchant server: python manage.py tron_reconcile --limit 100

The no-PII owner revenue summary can be obtained read-only through: python manage.py tron_revenue_audit --limit 5000

The output groups independently receipt-backed invoices by exact host and original catalog currency, records actual TRX SUN sums and flags incomplete ledger evidence. Revenue reports cannot mix USD and IRR/IRT totals without separate justified FX conversion. The management interface can use this command as the data source for the single organizational agent mojtaba.bot.ai.

### Configuration / release conditions

The safe flags and values are now explicitly wired to config/settings.py and the repository .env.example; they are all disabled or unset by default:

- TRON_UNIFIED_PUBLIC_ENABLED=False
- TRON_UNIFIED_DISCOVERY_ENABLED=False
- TRON_UNIFIED_SHARED_RATE_LIMIT_READY=False
- TRON_UNIFIED_RECEIVER=(verified public wallet address)
- TRON_UNIFIED_ALLOWED_HOSTS=(explicit routed hostnames only)
- TRON_UNIFIED_PRIVATE_DIGITAL_ROOT=(protected absolute path outside webroot)
- TRON_UNIFIED_TRONGRID_API_KEY=(private indexer key; no on-chain authority)
- TRON_UNIFIED_CACHE_URL=(private shared Redis instance)

Do not place production secrets, email addresses of customers, invoices, or private keys in any GitHub branch. The server's installed components, DNS, real cPanel source and email transport are not certified by this change. Real paid mainnet round-trip acceptance must be done on separately access-controlled mainnet staging using owner-approved real funds, then intentionally approved for each public host. Do not switch the live environment to public merely because unit tests pass. Existing private MojPlayWin guest TRX orders and settlements must remain accessible.

Automated read-only incoming history is a bounded window, not full historical completeness; older and anomalous transfers need manual reconciliation and possible compliant refunds. Digital delivery after paid settlement is implemented; physical/service fulfillment requires human or authorized workflow evidence separately.

### Evidence status

All source edits and deterministic/mock/database tests are committed to the review branch; no real payment, production deployment, Gmail send, wallet transfer, billed external service, or change to live cPanel settings is performed by this source PR. Check actual completed CI on the latest commit separately before merging. GitHub green checks are not proof of commercial revenue.

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

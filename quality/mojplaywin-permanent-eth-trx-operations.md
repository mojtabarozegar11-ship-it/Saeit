# MojPlayWin — Permanent native ETH/TRX checkout operations

**Status: candidate implementation only; NOT a live gateway activation.** This runbook applies solely to the main mojplaywin.com site and its canonical product pages. The unchanged sitewide crypto engine is on `feat/mpw-customer-checkout-minimal-20261015`, diverged from current `main`; do not merge that entire branch. The implementation and its database migrations/routes must be selectively integrated into a proven isolated tenant runtime first.

## Invariants
- Keep the 17 × 20 home unchanged and preserve every existing page, paragraph, image, product and URL.
- Never change or restart the shared Passenger/Django runtime or any independent /saman/, /studio.Roham/, /farnaz/, /zahra$$/, /taniya/, /picm/, /mojtaba.roozegar/ or unknown subsite. Do not touch Zomorod Melal.
- Only **native ETH on Ethereum mainnet** and **native TRX on TRON mainnet**. USD is a pricing unit, not an alternative processor. Stripe must not be added.
- Receiving-wallet ownership signatures must be validated. Merchant private keys and seed phrases must **not** be stored in site code, public directories, client JS, CI logs or prompts.
- Customers may place orders without per-purchase merchant intervention, but product publication/licensing/quality is approved once and must remain independently revocable.
- No product can be billed until customer login, verified private deliverable, quote source, invoice uniqueness, receipt confirmation, idempotent ledger and entitlement are proven.

## Workflow, permanently reusable across eligible products
Registered Product -> approved price/fulfillment -> authenticated customer's order -> signed buyer wallet challenge -> locked USD-to-ETH/TRX server quote -> exact chain-specific invoice -> bounded recurring discovery -> independent finalized on-chain RPC proof -> atomic ledger/order receipt -> idempotent digital download/course enrollment OR queued service/physical dispatch -> buyer history.

The existing `mpw_commerce.policy.order_snapshot` supports multiple order lines and `digital / subscription / service / physical` fulfillment kinds. The existing public customer order view currently permits just a single eligible paid digital SKU per order. **Do not claim all those fulfillment categories can already be purchased online** until their customer order forms, delivery handlers and refund workflows are tested.

## Required release/operations gates
- All eight `MPW_COMMERCE_*` release gates checked by `core/mojplaywin_catalog_readiness.py`; additionally `MPW_COMMERCE_ISOLATED_RUNTIME_CERTIFIED=True` and `MPW_COMMERCE_CONTINUOUS_OPERATIONS_ENABLED=True` on an actually isolated production tenant.
- Install the original `mpw_commerce` and `mpw_native_checkout` apps and correct migrations **only** after a full isolated restore drill and URL/routing isolation. Verify known and unknown child-site protections and automatic rollback.
- Enable `MOJPLAYWIN_NATIVE_CATALOG_ENABLED` only after tenant-scoped product inventory audit. `MOJPLAYWIN_NATIVE_CRYPTO_CHECKOUT_ENABLED` must stay OFF until real paid purchase→finality→delivery canary passes.
- Every product separately requires `mpw_commerce.enabled`, correct fulfillment kind, protected private-file proof when digital, approved price/license/quality, final published article, verified exact receiving accounts, and owner release.
- The operator must verify actual production chain/indexer connectivity, rate quote freshness and wallet control, not infer readiness from old CI or sandbox signatures.

## Independent once-per-invocation operation (NOT installed or scheduled yet)
After the above gates pass on a dedicated runtime, a trusted cPanel/VPS scheduler may invoke, from the isolated MojPlayWin project directory:

```sh
python3 scripts/mojplaywin_crypto_permanent_worker.py --check
python3 scripts/mojplaywin_crypto_permanent_worker.py --once
```

The `--once` mode runs the existing `mpw_commerce_reconcile` then `mpw_commerce_fulfill_courses` management commands, with an exclusive lock in a pre-existing private **0700 directory outside all webroots**, a two-minute timeout for each command, no output of potentially sensitive process logs and nonzero failure status. Configure `MPW_COMMERCE_PRIVATE_LOCK_PATH` to that existing absolute private lock filename. Use an external supervised scheduler with bounded frequency (e.g. every 2 minutes), overlap prevention and alerts; this script **does not create cron, daemon or any external schedule**. The worker intentionally refuses to start on a shared/unverified site and never signs outgoing transactions.

## Acceptance tests before public checkout
1. Genuine signed receiving-wallet ownership for both networks, mainnet trusted indexer/RPC finality, FX quote staleness, wrong chain/address/amount rejection, duplicate event replay and transaction reorganization.
2. One small owner-funded ETH and one TRX canary covering invoice, actual finalized inbound transfer, ledger, customer purchase history, one-time entitlement and secure file download.
3. Partial, wrong-network, overpaid, late-after-expiry and deposits during RPC outage must enter a documented review/recovery queue; they must **never** silently grant access or disappear from an audit report.
4. All customer logins, 403/404 access separation, licensing restrictions, service fulfilment and course enrollment tested before advertising those classes as saleable.
5. Verified full DB/files restore, SHA-pinned release artifact and atomic path-scoped rollback, exact before/after protection of every independent subsite, no Passenger restart.
6. Recurring worker heartbeat and recent successful reconciliation visible to operator; notify after consecutive failed cycles; seller controls pause without erasing orders/history.

**Current public observations (2026-10-18):** `/api/products/` returns an empty JSON array. `/store/` lists six informational collections, not live paid SKUs. An independent verified *free* calculator is downloadable from `/factory-releases/farm-enterprise-economics-v1/`. No live ETH/TRX canary or continuous scheduler proof is available yet. Therefore public paid checkout and release flags remain OFF.

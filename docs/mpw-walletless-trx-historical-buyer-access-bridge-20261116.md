# Already-paid native TRX buyer: fail-closed historical digital access bridge

## Business incident / actual production evidence
- Live Actions 43774135363 proves that at least one existing nonstaff-account native TRX transaction was independently solidified on Mainnet and precisely attributed to the owner QR receiving wallet, original sun amount, sender and original TXID.
- Same core OrderItem is active, not game_cosmetic; a same-item CommerceFulfillment READY row already exists. No refund/reversal in inspected paid order.
- No CommerceInvoice belongs to that **same core.Order**, so the existing mpw_commerce entitlement function demanding CommerceInvoice+CommerceReceipt rejects the buyer. The customer must **never be asked to pay again** merely because the two sources of truth were not joined.
- Exact, no-PII runtime evidence: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43774135363 ; P0 issue https://github.com/mojtabarozegar11-ship-it/Saeit/issues/2462 .

## Implemented read-only decision
`services/mpw_walletless_existing_paid_access.py` exposes
`verified_existing_walletless_item_access(request.user, core_order_item_id, asset_is_releasable=trusted_private_asset_resolver)` and returns a **boolean only**. It does NOT create an invoice/receipt or manipulate the live order.

To return True, it requires ALL of these actual database and client-session facts:
1. Separate release flag `MPW_WALLETLESS_EXISTING_PAID_DIGITAL_ACCESS_ENABLED` set to literal Python True on the server (Django env default **False**).
2. Authenticated, active and existing request.user; item record owned by that exact user; strict integer IDs, no anonymous/token-only claims.
3. Existing core Order.status=paid, same USD buyer item and exact paid PaymentIntent provider=`mpw_walletless_trx_v1`; positive units, correct owner-verified TRON recipient and sun amount from persisted invoice reference.
4. Existing independent `core.crown_tron_receipts.verified_walletless_credit` matching ledger and processed finalized event; no refund, reversal or chargeback entry.
5. The real CommerceFulfillment FK must target **core.orderitem** exactly and that same item's fulfillment status must be READY or COMPLETE.
6. The existing trusted server private-file resolver must independently verify real legally available digital asset, inside the correct private tenant. It MUST be a hardcoded trusted function in the authenticated download handler, NEVER browser text, caller-provided URL, or an unreviewed positive assertion. A missing asset denies access.

*Neither* a user's submitted TXID, PDF URL, screenshot, commerce receipt from another order, arbitrary product ID nor a paid checkbox grants access. A live owner blockchain payment is only supporting evidence; the specific buyer, order and asset must match.

## Integration still not performed
The current `mpw_commerce.entitlements` and download view are in the private production package, not in this public Saeit repository. This new module is **not wired into the buyer-facing download handler** and MUST NOT be advertised as live automatic delivery.

Only after a full independently verified isolated DB+media restoration and correct Passenger tenant isolation (issue #2392), review the exact live commerce handler source and add a narrowly scoped fallback to its existing authenticated customer download flow. Do not replace the normal CommerceInvoice path, change historical financial records, create fake CommerceReceipts, downgrade other permission checks or activate all products indiscriminately. Release requires exact file/rights tests, 100% non-owner denial, repeat GET and refund cases, merchant receipt and buyer acknowledgment.

The bridge has no writes, sends, RPC queries or settlement, and no automatic on-main deployment. Private files are never opened by this source module. Source-only CI tests include wrong actor, missing paid proof, wrong network wallet, wrong FK, wrong SKU, revoked payment, inactive product, incorrect private file, default-off, etc.

No new money, financial commitment, email, production release or live trade is authorized in this PR.

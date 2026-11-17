# MojPlayWin TRX — existing paid customer item and fulfillment classification

**2026-11-16. Zero-cost, zero-mutation P0 operational diagnostic.**

## Confirmed source and live baseline
- [Saeit PR #2457](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/2457) merged read-only DB evidence: at least one persisted walletless TRX Paid PaymentIntent and one matching stored finalized event/ledger receipt contract.
- [Run 43771138667](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43771138667) saw no positive `mpw_commerce.entitlements.can_access_purchased_digital_item` result for that paid order, but that **does not** prove nondelivery. The paid product type was not classified.
- `core.crown_fleet.owned_skus` explicitly handles `core.OrderItem.product.product_type == "game_cosmetic"` with `core.crown_tron_receipts.verified_walletless_credit` and a game fleet entitlement; **not** a downloadable file.
- The separate `mpw_commerce` package and `core` models must never be joined by coincidental numeric IDs; a Django FK must positively identify `core.order` or `core.orderitem`.

## Actual source implementation
- `scripts/mpw_trx_paid_product_scope_readonly_20261116.py` runs on the existing authenticated cPanel tenant, scans no more than 25 persisted walletless paid intents with no more than 30 core.OrderItem rows per order.
- It checks: ledger/receipt contract; whether buyer account is staff vs nonstaff (nonstaff is *not* proof of a first external customer); whether paid items are `game_cosmetic` versus other/unknown product_type; whether the same game cosmetic SKU is in that user's owned fleet; exact `core` foreign-key-based fulfillment only if such a relation exists; whether refund/reversal/chargeback exists.
- If the fulfillment schema belongs to another `mpw_commerce` order namespace, it correctly returns **unproven**, never joins on equal-looking integers. Unknown type is not automatically labeled downloadable.
- It emits aggregate BOOLEANS only: no buyer IDs, product IDs, emails, addresses, TXIDs, amounts, receipts, account names or payment details.
- It does not create/pay invoices, initiate downloads, send emails, trigger network payment calls, write a DB, modify a service or spend currency.
- A new pinned source-and-host step extends the existing owner-authorized self-hosted PR workflow; the script is byte-locked by its current Git blob SHA.
- A separate test module exercises 27 checks: product classification, exact relation, buyer role, no false external buyer proof, no customer download inference, wrong refunds, read-only process and workflow boundaries.

## Success criteria and boundaries
This diagnostic can tell whether an existing paid intent is a game cosmetic with account ownership, an unrelated digital/other product, or an owner/staff canary. It **cannot** prove an actual external buyer's consent, independent renewed TRON solidity finality, real net income, or receipt acknowledgment. If a true paid digital purchase is found without its rightful entitlement, fix only its scoped delivery path after independent DB/media backup and restore. Do not activate public canary or replay a TXID.

No production checkout change, payment, on-chain broadcast, monetary expense, live trading, customer outreach or deployment authorized by this source investigation.

## Independent real-chain verification (read-only)

- After the confirmed *existing* walletless TRX paid receipt and same-order READY fulfillment were observed, an additional source verifier was added, not an invoice or payment sender.
- `scripts/mpw_tron_one_existing_payment_solidity_readonly_20261116.py` reads at most **one** existing paid non-staff walletless settlement on the previously verified owner recipient, then issues at most **two** independent HTTPS calls to **exactly** `api.trongrid.io`, querying `/walletsolidity/gettransactionbyid` (canonical solidified transaction body) and `/walletsolidity/gettransactioninfobyid` (solidified execution receipt). Public chain txid is submitted only to the provider, not printed into CI or the file.
- Checks exactly one native TRX `TransferContract`, same sender, owner's Base58Check receiver, precise original `sun` amount, same txid, successful execution and positive solidified block/timestamp. No external customer ownership or download is inferred.
- No redirect, no proxy, no user-supplied endpoint, no private key, no purchase/transfer/signature, no fees, no source file write, no database mutation; maximum payload 100kB, 9 seconds each request, no retry. If anonymous Mainnet RPC is rate-limited (e.g. 429), result stays **unknown** and is not falsely marked failed or paid.
- This probe may be rate-limited by TronGrid and is run exactly once per reviewed PR workflow; only a redacted boolean result enters public logs.
- Tests cover checksum lookalikes, invalid TXID, wrong sender/recipient/value, wrong asset/contract, multisend, revert/failed execution, incomplete finality, no redirect and strict endpoint lock.
- Authoritative protocol: https://developers.tron.network/docs/confirmation-semantics and https://developers.tron.network/reference/gettransactioninfobyid-1 .

# Moj Prop Starter30 — native TRX buyer-order reconciliation contract

**Product:** `MOJPROP-STARTER30` (ten-session simulated journal and human-readable learning scorecard). **One-time indicative tariff:** exactly **30 native TRX = 30,000,000 sun**, **not** 30 USDT, 30 USD, or TRC-20 tokens. A simulated $100 equity reference never creates a funded account or a withdrawal right.

This document describes the exact *unmet* production integration gates. Source tests do not activate a merchant, order, live node or settlement.

## Verified existing code and missing integration

- `services/mpw_trx_merchant_binding.py` already checksum-validates TRON Base58Check and binds each domain/merchant identity to a server-managed recipient; browser input may never override merchant details.
- The owner QR-validated receiving address now exists in reviewed source as `services/mojtaba_tron_owner_receiver.py`, but this does **not** establish merchant legal eligibility, independent wallet custody reconciliation, enabled billing, or customer invoices. Keep invoice/solidity flags disabled until separately approved and independently verified.
- `services/mojprop_starter30_tron_settlement.py` only compares **read-only, trusted solidified node observations** against an already issued immutable, signed-offer, buyer-consented database invoice. It must reject even a *checksummed, valid* recipient different from the exact owner-approved wallet. Error fields returned by the node are fatal even if their value is empty/falsey.
- The existing `MojPropOffer` quote is **USD/IRR-only**; do not mislabel a USD 149 blueprint or rewrite an old USD offer as 30 TRX. A separate reviewed native-TRX order/settlement model or a reconciled, schema-safe store adapter is required.

## Order issuance (NOT implemented)

1. Authoritatively verify seller legal eligibility, accurate business identity/jurisdiction, refund/chargeback policy, owner wallet custody and permitted payment category. Do not infer compliance from absence of a KYC request.
2. Establish complete site/db/media backups and a successful **independent** restore; prove isolated production app/docroot and block unrelated tenants.
3. Verify the customer-provided contact email, informed consent and unexpired reviewed written terms. Customer's `buyer_terms_acceptance` must be an authenticated, independently saved reference. Do not collect buyer funds from a mere enquiry form.
4. Create one server-side, unique, immutable order reference `MOJPROP30-[A-Z0-9]{12,32}`, with strictly `merchant_domain=mojplaywin.com`, `merchant_id=mojplaywin-store`, `network=tron-mainnet`, an owner-approved canonical checksummed recipient and exactly **30,000,000 sun**. Order expiry no longer than 24 hours. Never create a payable invoice from a browser-supplied recipient or amount.
5. For automatic assignment on a *shared* receiver, first bind an authenticated customer to a proven sender address. Payments from exchanges or different senders need manual, authenticated reconciliation — a copied public txID is not proof that a customer owns it.
6. Publish a payment UI only after a real cPanel deployment, verified HTTP purchase flow and documented buyer invoice, confirmed refund rights and unique delivery/receipt path. Until then, Starter30 is inquiry-only.

## Atomic on-chain confirmation (NOT implemented)

1. Use an authenticated, known mainnet SolidityNode endpoint, not a broadcast result nor a generic `/wallet` FullNode observation.
2. Query `POST /walletsolidity/gettransactionbyid` using the exact 64-character txID; confirm a *single* `TransferContract` with sender/recipient and **30,000,000 sun**, successful contract result.
3. Query `POST /walletsolidity/gettransactioninfobyid` from the same authenticated mainnet node. Require matching `id`, positive `blockNumber`, successful execution and a **solidified block timestamp within the invoice window**. Unknown, incomplete, mixed-node, error or late responses must not mark paid.
4. Under one database transaction use a `UNIQUE(txid, network)` constraint with a unique invoice/order relationship. Check sender-ownership proof, order's permitted state, amount/expiry and chain consistency atomically. A Python `frozenset` of prior transaction IDs is *only* an early advisory replay screen, not a concurrency lock.
5. Only after persistent unique assignment and required approvals issue the buyer receipt and safe digital delivery, and record actual received revenue; ensure duplicate webhook/poll callback idempotence. Never log buyer PII, private keys, mnemonic or paid access tokens in public CI.
6. Unexpected amount, wrong native asset, late tx, refund, duplicate txid, non-original sender, and timeout must enter manual review. Payment on-chain is irreversible; do not mislead the buyer about cancellation.

Official sources:
- https://developers.tron.network/docs/confirmation-semantics
- https://developers.tron.network/reference/gettransactionbyid
- https://developers.tron.network/reference/gettransactioninfobyid-1
- https://developers.tron.network/docs/tron-contracttype

**Explicit invariant:** the existing pure candidate checker returns `buyer_entitlement_granted=false`, `receipt_sent=false`, and `revenue_booked=false` even when its two supplied offline proofs match. The live signed-node and database ledger are not implemented by this module; it must never be represented as a live payment gateway. New funds, subscriptions, fees, live trades or customer emails remain owner-prohibited without required release proof.

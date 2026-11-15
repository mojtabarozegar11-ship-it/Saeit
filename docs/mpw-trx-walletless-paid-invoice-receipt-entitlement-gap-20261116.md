# Walletless native TRX already paid: pinpoint missing receipt or buyer-download link (P0)

This is a **read-only production-root-cause investigation** of a real, previously paid Mainnet TRX transfer confirmed in [Actions 43773174146](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43773174146): correct receiver, sender, amount, txid, finalized block/receipt. The Django core ledger has a valid stored paid receipt; the same non-cosmetic order has a CommerceFulfillment READY record. A prior entitlement function check returned FALSE. No new money is moved.

The existing `mpw_commerce.entitlements.can_access_purchased_digital_item` source uses CommerceInvoice+CommerceReceipt+CommerceFulfillment+LedgerEntry; a walletless direct order may have a legitimate core LedgerEntry but not a corresponding CommerceInvoice, causing paid-buyer access denial. **That is a hypothesis until the actual live FK-linked rows are inspected.**

New `scripts/mpw_trx_existing_buyer_entitlement_link_readonly_20261116.py` checks only:
- At most 25 previously paid walletless TRX orders from an explicitly nonstaff user and at most 30 OrderItems for the selected verified order.
- Existing core walletless `verified_walletless_credit`, refund/reversal exclusion and non-cosmetic item.
- Exact `core.order` foreign key from the `mpw_commerce.CommerceInvoice` model, and whether the paid invoice exists for **the same order**, without printing private IDs.
- Exact `mpw_commerce.commerceinvoice` FK from the Receipt model and whether **the same paid order's invoice** has a receipt.
- Exact `core.orderitem` FK from CommerceFulfillment, READY/COMPLETE state on the same item, and the current read-only entitlement checker invoked only if its model is `core.orderitem`.
- A P0 classification based on those actual FK-linked booleans, **never on a coincidental numeric match across app models**.

The script prints only bounded booleans; no IDs, amounts, user email, wallet keys, transaction hashes, buyer tokens, asset paths or hidden file content. It never grants entitlement, creates invoice/receipt, contacts a blockchain node itself, sends mail or changes Django rows. It is pinned by a Git blob fingerprint and run through owner-authored self-hosted GitHub Actions read-only cPanel connection with no main push trigger.

**Release decision after proof:** if the invoice is missing, don't backfill a fake paid receipt. A real validated walletless credit needs a formally designed reconciliation adapter with unique payment-to-buyer linkage and real product digital-file availability; verify isolated DB/media backup/restore before any live write, require consent and actor authentication. If invoice and receipt exist but entitlement denies, inspect the downstream exact input, storage path and refund gates privately. Never disable the canary to force acceptance.

This stage does not establish external customer identity, delivered download, new cash revenue, seller income amount or net profit. Related issue: https://github.com/mojtabarozegar11-ship-it/Saeit/issues/2462 .

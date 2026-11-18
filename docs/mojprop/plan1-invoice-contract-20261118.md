# MOJ-PROP-01 — Plan 1 invoice contract

This release adds the missing backend contract for the real Plan 1 offer:

- exact price: 30 native TRX = 30,000,000 SUN;
- canonical SKU: `MOJ-PROP-01`;
- canonical contract: `2026-11-15/v1.2`;
- exact merchant scope: `mojplaywin.com / mojplaywin-store`;
- bounded invoice lifetime: at most 24 hours;
- trusted bilingual contract digest and buyer acceptance;
- protected TRON recipient and optional pre-bound payer;
- independent gates for jurisdiction, capital, broker compatibility, identity screening, terms, refund handling, settlement reconciliation and the effective route.

The module does not itself create a database invoice, send email, call TRON, or grant a funded account. The next integration step is the cPanel gateway adapter: persist this snapshot, enforce a global unique `(network, txid)` ledger, and call the existing solidified-node reconciler only after an owner-approved legal/treasury release.

Therefore this commit closes the invoice-contract gap but does not claim a live paid sale.

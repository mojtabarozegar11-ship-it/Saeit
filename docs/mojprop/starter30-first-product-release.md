# MOJPROP-STARTER30 — single-product launch and release contract

**Status (2026-11-15): SOURCE-ONLY / NO-PAYMENT / NO-LIVE-FUNDING.**
This contract creates an independently reviewable English educational product,
not a funded trading challenge. Public sale, TRX transfer instructions,
broker/payout claims and customer commitments remain BLOCKED until evidence
from the actual seller, host and payment rail is independently verified.

## Product and fulfilment

- Product: Moj Prop Starter 30; operator identity: mojtaba.bot.ai.
- Indicative fixed service fee: **30 native TRX** (30,000,000 sun). The on-chain
  transfer fee, if any, is a separate network expense; it is not a sale receipt.
- Buyer: an adult customer in a lawful supported jurisdiction after applicable
  consumer and crypto-payment obligations are satisfied.
- The $100 reference figure is **simulated USD**, NOT client funds, broker
  equity, a funded account, available cash or a withdrawal entitlement.
- Ten consecutive self-reported sessions with closing simulation equity,
  explicit risk-plan and reflection indicators. Daily loss over 3% and
  peak-to-trough drawdown over 6% are reported as coaching concerns.
- Deliverables: (1) journal guidance/template (2) deterministic risk report
  (3) individualized written recommendations based on consented submissions.
- Manual review of submissions is necessary: the scorer cannot verify any
  simulated results as real trades.
- The 30 TRX product contains **no** capital allocation, 100 USD funded
  account, cash payout, prize, investment service, auto-execution, broker
  connection, guarantee or entitlement to a later account.
- For a separate *funded* challenge at 30 TRX, retain legal/capital hold under
  Karegar #15 until seller identity, jurisdiction, capital commitments, written
  broker arrangement, customer contract, KYC/AML and payout reserve are proven.

## Twenty evidence-bound commercial release gates

1. Confirm legal seller's exact legal name, registration and country.
2. Confirm countries and customers to which this educational product can lawfully be offered.
3. Document whether seller needs any registration, tax, consumer or crypto-payment compliance.
4. Approve English contract and precise training-only scope.
5. Publish seller contact, privacy and customer complaints channel.
6. Publish cancellation/refund terms including what happens if payment is misdirected.
7. Publish service delivery deadline and buyer acceptance criteria.
8. Confirm educational exercise/journal and actual personalized report can be delivered.
9. Verify rights to every included text/template and customer-facing sample.
10. Verify main branch CI at the exact released commit; no red job ignored.
11. Verify Passenger/cPanel document root and tenant isolation read-only.
12. Preserve live files and independently test backup/restore/rollback before releasing.
13. Do NOT activate the unsafe migrating Django backend; resolve Saeit #2392
    (DB migration and post-failure restoration proof) before any backend change.
14. Verify the live root GET intake and customer receipt routes without creating fake leads.
15. Verify a consented buyer request can be uniquely identified and tracked.
16. Confirm owner-controlled TRON **mainnet** receiving address and lawful custody;
    never disclose a candidate address or private key in repo/public pages.
17. Issue a uniquely identifiable customer-specific invoice for exactly 30,000,000 sun
    on the native TRON network; prevent ambiguity between equal-value deposits.
18. Confirm recipient and native TRX amount from the actual TransferContract, uniquely
    bind transaction ID to exactly one order, and require SOLIDIFIED inclusion on
    /walletsolidity/gettransactionbyid; never treat broadcast as settlement.
19. Reconcile underpayment, overpayment, duplicate/replayed txid, expiration, refunds
    and exceptions into an immutable ledger with signed receipts.
20. Release the service **only after** 1–19 are evidenced; verify one real,
    consented buyer request -> legal invoice -> solidified settlement -> actual
    scorecard + recommendations delivery -> buyer receipt, then record real income.

### Fail-closed release decision

- Source/CI completed is not production deployment.
- Public HTTP 200 is not a lawful offer, completed order or payment.
- No shared receiving address + manual "I paid" screenshot can automatically
  mark paid. The receiver, amount, txID, customer order and solidification must
  all be cross-checked; txID cannot be reused across orders.
- Do not merge this file into a public **checkout** flow merely to hit a deadline.
- Public landing is marked `noindex` until a reviewed and actually published
  commercial release; then recheck SEO, sitemap and canonical.
- No financial transaction, external message, owner fund transfer or expense
  is authorized by this runbook.
- Old commercial offer catalog (4 services in USD) must NOT silently use
  `blueprint` starting at $149 as the 30 TRX price; dedicated SKU order contract
  and manual quote provenance are required first.

## Source acceptance

`python3 -m unittest tests.test_mojprop_starter30_contract -v`

Release code can be merged only after independent CI and no-auto-deploy checks.
The sample HTML file is intentionally **not** in the existing six-file static
publisher allowlist. It must not be publicly linked as live before an approved
publisher release with exact SHA, proven host baseline and all above controls.

## Source citations and open issues

- Internal funded-capital hold: Karegar issue #15.
- Production DB migration mismatch: Saeit issue #2392.
- TRON solidification: https://developers.tron.network/docs/confirmation-semantics
- TRON native transfers: https://developers.tron.network/reference/transactions
- UK risk warning example (specific unauthorised firm, not a blanket ban):
  https://www.fca.org.uk/news/warnings/funded-trader

**Accounting:** Recognised received revenue = zero until a real,
independently confirmed settled order is reconciled and delivered.

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

## Actual single-SKU delivery assets (added in current cycle)

- `templates/moj-prop-v4/starter-30-trx/index.html`: English standalone information page with two free download CTAs; it is not currently live and remains `noindex`.
- `templates/moj-prop-v4/starter-30-trx/journal-template.csv`: ten-session completely blank customer journal. The template intentionally has **no invented profitable entries**.
- `templates/moj-prop-v4/starter-30-trx/journal-guide.txt`: explicit fields, legal boundaries, risk and submission instructions.
- `scripts/mojprop_starter30_journal_csv.py`: bounded UTF-8 CSV import; strict 10-session identifier order, monetary decimal validation, yes/no flags and injection rejection.
- `scripts/mojprop_starter30_scorecard.py`: user-independent printable individual feedback. Case ownership must be authenticated by the actual operator before any private delivery.
- `scripts/mojprop_starter30_static_release.py`: **manual and static-only** three-asset release with tenant identity checks, explicit one-time approval, no overwrite, digest manifest, private permissions and strict rollback. No automatic workflow, migration, wallet or payment integration. Source-only until actual host access and verification.

### Precise static release procedure (NOT authorisation to run)

1. Obtain current GitHub HEAD SHA and separately verify each asset's SHA-256 against the approved source; stage all three exact assets into the dedicated per-run private cPanel staging directory. Staging source integrity is an **external prerequisite**; an untrusted staged tar is not approved by a matching CLI commit string alone.
2. Verify in a read-only cPanel session the current `/home/zomorod2/mojplaywin.com` effective docroot, expected Passenger/`.htaccess` tenant, existing `/moj-prop/` directory and sufficient space; separately record a successful independent site backup and isolated restoration rehearsal.
3. On the correctly authenticated account, execute **preflight only**: `python3 scripts/mojprop_starter30_static_release.py preflight RUN_ID REVIEWED_COMMIT`; compare every reported asset digest with the verified source record.
4. Complete legal seller, jurisdiction, customer terms, delivery owner, lawful TRX merchant and no-conflicting-automation checks. Without these, do not publish a pay-enabled page or collect funds.
5. A specific release approval must be recorded. Only then may an operator run `MOJPROP_STARTER30_OWNER_APPROVED=static-only-approved python3 scripts/mojprop_starter30_static_release.py deploy RUN_ID REVIEWED_COMMIT`. This adds three files at one exact, owner-controlled path. It never creates a payment method or changes Django.
6. Verify live HTTP 200 + exact bytes at the three expected paths and customer content; if verification fails, run `rollback RUN_ID REVIEWED_COMMIT`. Never delete user-modified files to force a rollback.
7. Leave public page `noindex` and avoid linking from the commercial catalog until all legal/merchant gates are complete, and then perform a separately reviewed SEO/public link release.

**Important:** this publisher is a one-time **new path only** installer. Subsequent revisions must use a reviewed new update protocol; do not overwrite existing customer-facing files with the initial installer.

### Added regression suites

- `python3 -m unittest tests.test_mojprop_starter30_journal_csv -v`
- `python3 -m unittest tests.test_mojprop_starter30_static_release -v`
- `python3 -m unittest tests.test_mojprop_starter30_public_offer -v`

**Not production evidence:** script and test success alone do not prove public site release or received revenue. A manual inquiry is not a completed sale.

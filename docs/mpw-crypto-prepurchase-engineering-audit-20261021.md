# MojPlayWin crypto payment and automatic delivery — Pre-money engineering audit

Date: 2026-10-21. Scope: **MojPlayWin native cryptocurrency (TRX/TRON and enabled ETH) only**, payment receipt and private digital delivery. No bank cards, fiat-to-crypto onramp, or money movement.

## Production audit proof

**Read-only production audit**: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39552068488 (all steps successful). No production SQL writes, new sales, or chain transfers.

- 7/7 in-scope Django commerce feature flags are enabled: release, customer HTTP, invoicing, settlement, real RPC, automatic reconciliation, private downloads.
- Production API routes resolve for order → challenge → signature verify → invoice → status → download. Payment pages for products 72, 225, 779 render 200, have the strict script CSP and automatic status update marker.
- One operational crontab worker executes every minute with `flock`; the most recent 1,200 observed worker log entries all report **idle** with no errors in that sample. There are **zero orders, invoices, receipts, ledger entries and fulfillment entries** in the live database at the audit time. Idle means no pending invoices; it does not exercise reconciliation of a real TX.
- Real read-only mainnet discovery APIs: TRX **readable**, ~0.86s, zero events; ETH **readable**, ~0.30s, zero events during their respective ten-minute windows. This checks discovery transport only, **not independent finality verification of a buyer payment**.
- Anonymous GET requests for status and download returned HTTP 302, not a PDF. Additional logged-in other-customer denial was verified in a mocked purchase simulation.
- Actual Django payment settlement code checks fixed invoice parameters, network, recipient, sender, exact atomic amount, timestamp within quote window, finalized flag, chain proof backend, matching transaction, unique receipt and atomic ledger/digital entitlement.
- Runtime payment-status UI polls automatically and only displays private, server-returned download paths after a verified entitlement. A real paid purchase is still unproven.

## New independent negative engineering suite

The Python script `scripts/mpw_simulated_crypto_purchase_delivery_20261021.py` runs **actual deployed Django business functions**, but with an isolated in-memory ORM and a temporary fake PDF; it cannot write a real financial record.

All **14 invalid proof scenarios rejected**: different order, network, sender, receiver, amount underpaid, amount overpaid, no finality, nonboolean finality, wrong TX, wrong proof backend, mined before invoice, mined after expiry, missing block time and stringified atomic amount.

Additionally:
- In-memory valid finalized proof produces exactly one simulated receipt, one simulated ledger record, one grant, and a buyer-only PDF download.
- Reusing the same paid TX does not create a second receipt or grant.
- Replacing the paid TX is denied.
- Missing blockchain receipt, ledger record, or fulfillment grant denies entitlement (using real Django reverse OneToOne semantics in test mocks).
- Unpaid request and unrelated customer cannot fetch the simulated private PDF.

Evidence: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39552068488 ; status successful.

## Engineering findings and decisions

| Level | Finding | Current decision |
| --- | --- | --- |
| Pass for isolated test | Atomic settlement, exact proof field matching, duplicate protection, linked receipt/ledger/grant checks | 14 negative scenarios plus successful fake-PDF simulation passed |
| Pass for deployed read-only inspection | Mainnet TRX/ETH indexers respond, worker schedule active and fresh, protected routes, authorization | Verified without actual funds |
| **P0 pre-commercial certification** | No confirmed real mainnet TX and no proven final wallet settlement / customer-file delivery | **Do not claim 100/100 or completed real purchase**; requires separately authorized small real payment and independent blockchain proof |
| **P1 operations** | The legacy release workflow `.github/workflows/mpw-simulate-automatic-crypto-delivery-20261021.yml` retries *installation* on subsequent pushes and fails because status auto-polling is already installed. | Treat as a release-workflow idempotence defect; use the separate successful **read-only** diagnostic workflow for repeated audits; do not overwrite live checkout or remove protected rollback solely to make CI green |
| **P1 resilience** | No evidence that automatic reconciliation completes after a real indexer outage, long downtime, refund, wrong token, or production load | Test isolated faults and recovery before final commercial signoff |
| **P1 buyer UX** | Crypto checkout currently depends on authenticated customer flow; an independent guest crypto checkout is not yet proven | If guest crypto checkout is required, implement independently without weakening verified entitlement |
| Deferred | Cards/bank transfers, fiat onramp, fiat KYB | **OUT OF CURRENT SCOPE**, not a crypto-only payment defect |

## Safe next action

1. Preserve present real-site checkout and payment-recognition code unchanged. Separately fix and test the repeat-run release CI condition without loosening rollback controls.
2. Complete outage, expired invoice, wrong asset, reorg/finality, mixed-order, and concurrency tests with mocked chain sources.
3. Only then request owner permission for a small **real native TRX mainnet** purchase. Require identical order, invoice, merchant receiver, sender proof, atomic value, finalized on-chain TX, single receipt and ledger entry, private product-specific download and post-purchase retrieval. Never mark a real order as paid from mock evidence.
4. Re-run the independent **crypto-only** 10 × 10 = 100/100 acceptance policy. As of this audit, the gateway's **100/100 certification remains BLOCKED**.

No bank payment service has been onboarded or activated. No API keys, wallets, secrets, customer information or transaction identifiers are published in this report.

# Sole mojtaba.bot.ai — Revenue evidence gate & operational snapshot
Date: 2026-11-14 — Source-only Draft; **not deployed**.

## Defect
An internal order marked `paid` and a shared-secret-signed payment callback do not prove independent settlement. Calling such data collected cash or net profit misleads the management desk, causes unsafe self-funding decisions, and hides failed fulfillment. Previously there was no single, owner-only, bounded reconciliation endpoint connecting the existing Order, OrderItem, PaymentIntent, LedgerEntry and PaymentWebhookEvent records for the sole master agent.

## 20 implemented, independently testable controls
1. Reconcile records **read-only** without modifying order, payments or ledger.
2. Limit the overview to a fixed 30-day window by default.
3. Cap query rows at 200; report whether the sample is complete.
4. Accept bounded integer day/row limits only (no boolean coercion).
5. Admit only the authenticated, active superuser owner to HTTP evidence.
6. Allow HTTP GET only, private/no-store, no reusable cache.
7. Redact buyer emails, payment secret, wallet address and provider references from output.
8. Distinguish `paid` from `pending` and other order statuses.
9. Require finite strictly positive exact Decimal order amounts.
10. Require normalized uppercase, bounded currency values.
11. Require bounded, nonempty order item inventory.
12. Validate item quantity and positive unit price.
13. Enforce order/item currency agreement and exact line-total reconciliation.
14. Require an associated payment intent matching the exact order.
15. Reconcile intent currency and exact amount, rejecting mismatch.
16. Reject demo/test/not-configured provider identities and malformed idempotency/reference values.
17. Detect duplicate provider references across payment intents.
18. Detect any refund, reversal or chargeback ledger record.
19. Reconcile provider-specific internal receipt: TRON via existing walletless consumer; other providers require one linked payment ledger and one processed, digest-bound webhook.
20. Never promote internal evidence to independently settled cash, verified profit or delivered goods; expose explicit `null` and `false` for unverified facts.

## New operational surfaces
- `core/revenue_evidence_gate.py`: bounded evidence resolver and aggregated snapshot.
- `command_center/revenue_evidence.py`: owner-only read-only endpoint, registered at `/staff/command-center/api/bot/revenue-evidence/`.
- `core/management/commands/mojtaba_revenue_evidence_readonly.py`: read-only CLI using same data model; no external system access.
- `core/economic_master_agent.py`: `inspect_revenue_evidence_readonly()` on the existing canonical master (no new bot).
- `core/tests/test_mojtaba_revenue_evidence_20261114.py`: 50 isolated Django tests covering amounts, statuses, customers, reversals, duplicates and public access.
- Scoped CI also runs existing walletless TRX entitlement and funnel instrumentation regressions.

## How to interpret output
- `sampled_order_count` is **not** all lifetime orders.
- `internally_consistent_nominal_not_cash` is face value of internally consistent test/live DB rows. It is **not** bank balance, settled income, deposit, wallet balance, tax revenue or net profit.
- `externally_settled_cash: null`, `verified_net_profit: null` and `revenue_claim_allowed: false` persist until **separate adapter and independently verifiable payer/chain/bank receipts** exist.
- An imported `tron_finalized` event is still a DB record; the existing chain verifier is an external dependency whose verified runtime cannot be established from this GitHub source alone.
- No email, payment, broker order, migration, deploy, real URL write or customer-data access was performed by this change.

## Remaining production gates
Independent live domain/provenance checks, deployed branch audit, legal payment settlement proof, buyer identity/email consent verification, correct-product delivery/receipt and reconciliation against bank or independently finalized on-chain state. Do not remove approval or risk controls without an auditable, equally binding substitute.

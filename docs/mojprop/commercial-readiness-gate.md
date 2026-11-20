# MOJ PROP commercial readiness gate

Status: internal source gate, not a payment release.

The English MOJ PROP page currently supports manual requests and explicitly
states that paid challenges, live accounts, KYC, automatic payment and profit
guarantees are inactive. This document defines the evidence that must exist
before a public paid route can be considered.

## Required evidence

1. Final product contract and customer deliverables.
2. Published risk rules and invalidation conditions.
3. Simulation disclosure that is visible before commitment.
4. Country, jurisdiction and eligibility boundaries.
5. Verified KYC and age-provider readiness.
6. Refund, support and dispute handling.
7. Server-issued invoice and exact amount controls.
8. Independent payment reconciliation and replay protection.
9. Delivery, receipt and customer recovery evidence.
10. Owner-recorded release approval.

The evaluator also requires explicit runtime control values for both the public
route and payment. It only returns an evidence result; it never changes those
controls.

## Current measured state

- Public route: closed.
- Payment: closed.
- Invoice: not created.
- Settlement: not allowed.
- Revenue: no collected revenue evidenced.
- Database migration: not authorized by this gate.
- Live account and broker execution: not authorized by this gate.

## Release rule

A green source test is not a commercial release. The route remains closed until
the evidence gates, staging canary, independent operational review and a
separate owner-authorized production release are all recorded.

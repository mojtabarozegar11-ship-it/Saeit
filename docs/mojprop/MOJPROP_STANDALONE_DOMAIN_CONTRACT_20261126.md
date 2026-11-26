# MojProp.top standalone commercial contract — 2026-11-26

## Owner decision

MojProp.top is a standalone business. It must not present itself as a subsite,
checkout, tenant, support desk or payment route of another brand.

## Three commercial lines

1. **Prop** — Starter30 simulated challenge and performance review.
2. **Signals** — educational signal desk with scenarios, rationale and invalidation.
3. **Education & Reports** — written market briefs, risk journals and trading education.

The public homepage now describes these three lines and sends the education/report
line to a manual request route until its standalone checkout is proven.

## Boundary implemented in this change

- Canonical, Open Graph, structured-data and visible brand references on the two
  MojProp home templates point to https://mojprop.top/.
- MojProp home links no longer send a buyer to an external merchant checkout.
- Shared legacy commerce routes are host-guarded on mojprop.top and return a
  non-payment 503 response instead of issuing or displaying another tenant's
  invoice.
- The guard is fail-closed and does not enable payment flags.

## Required before commercial activation

All of the following must be evidenced independently for MojProp.top:

1. Dedicated production document root and HTTPS response.
2. Dedicated Django host/tenant identity.
3. Dedicated database alias enabled and migrated.
4. Isolated prop simulation tables present.
5. Isolated invoice and payment ledger present.
6. Dedicated TRON receiver binding for MojProp.
7. Unique invoice generation and expiry.
8. Independent chain verification.
9. Independent delivery storage.
10. Email/recovery path owned by MojProp.
11. Tenant cross-read and cross-write tests.
12. Restore from a valid database dump into isolated MariaDB.
13. Restore of delivery files.
14. Independent rollback rehearsal.
15. Backup hashes recorded.
16. Starter30 end-to-end canary with no real transfer.
17. Signal subscription entitlement canary.
18. Education/report manual fulfillment canary.
19. Production deployment parity check.
20. Live browser test on mojprop.top proving no external-domain checkout.

Until items 1–20 are recorded, MojProp.top must not accept TRX or claim an
active paid enrollment. A visible page is not evidence of a completed sale.

## Current truth

- Production payment activation: **closed**.
- Independent restore evidence: **absent**.
- Release gate: **closed**.
- Last observed checkout failure: invoice 54 returned HTTP 500; no payment was
  sent and no retry is authorized.

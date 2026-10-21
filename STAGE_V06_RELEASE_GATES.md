# MOJ Commerce v0.6 — seller console, alert signal and restricted recovery

**Source-only / DRAFT. NOT DEPLOYED, no merchant payments, no scheduled jobs.**

## Implemented

1. Responsive, accessible HTML seller console at `GET /moj-commerce/merchants/<merchant-uuid>/console/`. Server-rendered with Django autoescaping, owner-authenticated on every request. It exposes only the same tenant-scoped, read-only metrics as the v0.5 JSON endpoint. No buyer names, wallet receiving addresses, private file keys, txids or global seller data. Strict `no-store`, anti-framing, and content security headers; no third-party assets/scripts.
2. Operator scanner health now includes sanitized fixed-code alert classification, and management command `python manage.py moj_commerce_healthcheck --strict` emits one JSON line (no customer data), exiting nonzero only for warning or critical signals. It does not schedule itself or send email/SMS. `disabled` is `paused`, **never** `healthy`.
3. `python manage.py moj_commerce_recover_stale` is a read-only dry-run by default. `--apply` requires **PostgreSQL**, operator setting `MOJ_COMMERCE_RECOVERY_ENABLED=True` and acquisition of the existing financial scanner advisory lock. It can close only abandoned `ScannerRun` **audit records**, leaving all invoices, entitlements, funds, refunds and transfers untouched. An active scanner holding the lock blocks recovery.
4. Separate Django/PG test suites cover tenant isolation, XSS escaping, privacy headers, fixed-code alert contract, recovery disabled-by-default and stale audit recovery under the lock. CI contains no deploy credentials or payment capabilities.

## Not implemented (release blockers)

- Real 24-hour scheduling / alert transport / independent channel with acknowledgements, deduplication and operator escalation. The healthcheck is only an integration point for an approved external scheduler.
- Autonomous payment recovery is intentionally prohibited; manual review for mismatches is required.
- Live site `mpw_commerce` model/mapping audit, cPanel source confirmation, independent TRON RPC quorum, wallet proof/address pool readiness, private file malware ingestion, PostgreSQL backup + restore drill, rollback, user support/refund handling, security/legal review and low-value real TRX E2E test.
- No production route mounting; these endpoints exist only in the isolated Django source slice.

## Release verification

- CI: Django test matrix, PostgreSQL 16 race/recovery tests, and TronWeb crypto interop must all pass. Confirm migration consistency.
- Browser review: 320/390/1280px, keyboard, long product title, contrast, no leaked data or HTML injection, actual deployed template settings.
- Deployment: requires separate written owner approval for merge/production. Confirm remote device and staging `mpw_commerce`/Passenger model routing, backup restore, and rollback **before** any production change.
- Financial gate: no live checkout, receipt address exposure, transaction transmission, payout, token launch or public-sale enablement from this PR.

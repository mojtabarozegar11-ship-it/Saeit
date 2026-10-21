# MOJ Commerce — safe release gates, 2026-10-21

**STOP: Nothing in this branch is ready to receive funds or deliver customer files on the live site.**

| Gate | Current evidence | Required before use |
|---|---|---|
| Domain models & migration | Source only; test CI required | Django `makemigrations --check` and isolated tests PASS |
| Independent finalized TRX receipt | Operator interface and fail-closed guard | Real and independently reviewed SolidityNode checker with final receipt |
| Merchant wallet ownership | `verified_at` field only | Secure ownership challenge and/or audited offline address attestation |
| Private product ZIP storage | Secure filename and hash-verified serving code | Upload/antivirus scan and owner-controlled filesystem permissions |
| Authenticated buyer link | Django signed token + 5min + download quota | HTTP and session QA against real site |
| Live order binding | Not connected | Actual site ORM/checkout mapping with buyer, seller, exact USD/Sun, unique address |
| Automatic monitoring | TRON Autopilot draft worker only | Durable PostgreSQL worker, recovery, independent health checks and alerts |
| Idempotent entitlement grant | Code with DB uniqueness + select_for_update | PostgreSQL concurrency CI proof (separate job) plus crash-recovery and replay proof |
| Finance and compliance | Not assessed | Merchant eligibility, legal reviews, return/refund paths, sanctions/jurisdiction review |
| Paid mainnet E2E | None | Explicitly approved small test, buyer receipt, download and rollback proof |

**Do not set** `MOJ_COMMERCE_RECEIVER_ENABLED=True` until every relevant gate passes. Keep this as a draft PR, do not merge into `main` or activate any cPanel workflow.

## Research-led next-stage release blockers (still all live gates closed)

- [x] Source implementation: TRON V2 signed wallet-control challenge with strict single-use, expiry, per-owner ACL and cryptographic recovered-address comparison; production-proof enrollment and wallet UX **not** performed.
- [x] Source implementation: pinned read-only TRON SolidityNode transaction + receipt refetch matching amount, destination, block number and block time; one third-party RPC provider only, no live-mainnet validation.
- [ ] Integrate a second independently operated TRON finalized RPC and quorum/consistency policy; safe behavior under outage, rate limits and chain data disagreement.
- [ ] Audit, separately approve and configure production checker, wallet ownership challenge in real seller onboarding, customer order/quote creation and webhook signed delivery; checkout/worker integration still absent from live source.
- [ ] Production PostgreSQL migrations with backup/restore and zero-downtime cutover, rate limits, signed challenge anti-abuse, seller KYC/risk and merchant suspension, monitoring.
- [ ] Test one real authorized small mainnet TRX purchase through to private download and receipt, using independent test buyer; currently no such evidence.
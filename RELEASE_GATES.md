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
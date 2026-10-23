# MojPlayWin TRON Pay v0.4 — production release gates

| Gate | Present in isolated source | Proved on production | Required evidence |
|---|---|---|---|
| Merchant-authenticated invoice issuance | Yes | No | Actual store order tied to exact invoice |
| TRX mainnet independent finality checks | Unit-tested | No | One owner-approved confirmed TRX transfer |
| Unattended indexed inbound reconciliation | Source + tests | No | Scheduled worker heartbeat and correct buyer status |
| Atomic payment and fulfillment event | Yes, SQLite pilot | No | Production DB migrations and rollback |
| Signed automatic store delivery + retry | Yes, synthetic receiver | No | Real Django store entitlement + duplicate prevention |
| Buyer can access bought file | Not connected | No | Paid item download E2E test with independent buyer |
| Secure merchant-owned per-order receive addresses | Mechanism present | No | Demonstrated ownership of a pool of public addresses |
| Contingency, failed RPC, refund, double-pay | Partial tests | No | Monitored operational runbook, security review |
| Cross-browser and mobile wallet quality | Chromium mock only | No | Real Trust Wallet on buyer device |

## Release decision

**Fail closed: do not merge into production, auto-deploy, publish live customer addresses, or take real money until all release gates pass.** PR #774 is kept as draft. GitHub CI success checks code; only an actual mainnet purchase + site-verified digital delivery counts as operational acceptance.
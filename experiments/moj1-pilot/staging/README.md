# MOJ1 → MojPlayWin: synthetic, read-only staging only

This is an isolated GitHub Actions integration test, not a deployment or a new
checkout option at mojplaywin.com. Existing live checkout remains unchanged.
The MojPlayWin guest TRX checkout source
(mpw_guest_trx_20261020/guest_database.py) defines the referenced order shape.

1. The public Shasta verifier compiles and checks creation/runtime bytecode,
   governance, fixed supply and fully funded escrow without wallet keys.
2. The pure bridge requires that verifier's successful JSON proof and the pinned
   TESTNET_ONLY manifest. All four contract bytecode witnesses must be present.
3. Only a synthetic zero-value order with a negative ID, no wallets, no claim
   secret and no transaction hash is admitted. Actual orders, payment statuses,
   transfers and Mainnet flags are rejected.
4. Output is an informational test receipt, with payment, delivery and database
   writes disabled. No private DB, live API, VPS or cPanel is touched.

Workflow: .github/workflows/moj1-mojplaywin-synthetic-readonly-staging.yml
Artifact: moj1-mpw-synthetic-readonly-receipt (contains no customer data or keys).

Production gates remain independent security review, legal approval, mainnet
key management and production financial E2E tests. This receipt is NOT evidence
of a live MOJ1 payment integration or an authorized public token sale.

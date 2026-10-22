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

## Non-public review page (same Shasta proof)

The workflow now generates a responsive static MOJ1 information page and checks
it over localhost HTTP before packaging it as an Actions artifact named
moj1-mpw-isolated-staging-preview. It contains index.html, a sanitized synthetic
receipt, release-gates.json and SHA256SUMS. This is not a deployed URL and cannot
process a checkout. Keep this output in review until production gates are met.

The release gates intentionally remain false for independent audit, legal
approval, mainnet custody and authorized sale. No agent-generated proof may
substitute for an independent assessor or applicable approval.

## Owner-private VPS installation (no website route)

A separate branch-pinned workflow installs the freshly verified Shasta preview
to the githubops account only, in a new private directory:
.local/share/moj1-mpw-private-preview-20261022

The installer checks a fixed four-file tar allowlist, SHA-256 receipts, disabled
payment/sale flags, directory ownership and mode 0700, and reads the page back
over a temporary VPS localhost-only HTTP listener. It versions each release by
the source commit SHA, keeps previous revisions, and writes a small CURRENT
pointer. It never starts a persistent web server, publishes a public URL, uses
wallet keys, deploys smart contracts or edits the live MojPlayWin site.

Workflow: .github/workflows/moj1-private-vps-preview-deploy-20261022.yml
Installer: staging/vps_install_preview.py

Operator note: the private files are for review by the VPS owner; no access URL
exists until a separately approved, authenticated review endpoint is built.
For a rollback, validate an older release and update CURRENT deliberately.
Actual public launch remains blocked by the recorded independent audit,
custody, and legal release requirements.

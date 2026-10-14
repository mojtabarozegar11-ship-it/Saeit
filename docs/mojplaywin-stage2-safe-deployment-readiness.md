# MojPlayWin stage 2 — safe deployment and rollback readiness

Status: **PREPARED, NOT DEPLOYED**. Owner requested stage 2: backup,
version drift analysis, isolated restore drill and rollback preparation.
Production payment flags, routes, applications, customers and data remain
unchanged. This document does not authorize deploying or charging buyers.

## Verified engineering facts

- The full offline buyer lifecycle suite passed **68/68** using ephemeral
  MySQL 8: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38654218472 .
  Its blockchain receipts are test doubles, not money received.
- Read-only live cPanel audit:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38653612702 .
  `mpw_commerce` is not installed, migrations not applied to live MySQL,
  checkout invoice URL does not resolve, all feature flags are off.
  The shared product table had 190 products, 0 active and 0 orders.
- Public GET: homepage and store 200, /checkout/ 404.
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38654014177 .
- Private on-host, compressed full MySQL backup AND six checked code-source
  rollback snapshots completed:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38655256296 .
  The backup captured 86 tables, 0 nontransactional tables, verified gzip
  structure and SHA256, 0700 checkpoint directory, and 0600 private files.
  Neither archive nor credentials were uploaded to GitHub.
- Specific live/branch code checks:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38655333323 .
  `config/settings.py`, `config/urls.py`, `core/models.py`,
  `core/views.py` **differ** from the release branch.
  `core/commerce_views.py`, `core/urls.py` matched.
  **Do not overwrite entire live files or merge the entire divergent
  release branch to main.**

## Private rollback snapshot

A private timestamped directory under the cPanel account's
`~/.mpw-private-db-backups/` contains:

- `mysql-full.sql.gz` and `manifest.json` with size/checksum/table count;
- verified copies of the existing site `config/settings.py`,
  `config/urls.py`, `core/models.py`, `core/commerce_views.py`,
  `core/urls.py`, plus the MojPlayWin Passenger WSGI wrapper when present;
- restricted `.env` original and other necessary host configuration
  files, **not** recorded in GitHub, logs or artifacts.

Rollback materials should remain on private hosting storage, protected by
host account permissions and offsite independent backup policy. Having
a backup does not by itself prove a point-in-time, zero-data-loss rollback.

## Verified isolated restore

Restore rehearsal workflow:
https://github.com/mojtabarozegar11-ship-it/Saeit/actions/workflows/mojplaywin-stage2-restore-rehearsal.yml

- Rejects absent, stale, symlinked or corrupt archived data.
- Checks cryptographic digest of the SQL archive and private source-code
  snapshots.
- Creates uniquely named **temporary** cPanel MySQL database and user;
  restores there, checks table count and Django migration history, then
  deletes only resources created by that exact run.
- Never imports into or deletes the live database. This tests restorability,
  not an automatic production rollback.

## Release patch — prepared gate, no application yet

1. Specify exact minimal diff against **running** source: add isolated
   `mpw_commerce` package, necessary migrations and carefully scoped URL
   wiring; do not replace shared `config/settings.py`, `config/urls.py`,
   `core/models.py` or `core/views.py` wholesale.
2. Demonstrate route resolution and backend compatibility in fully private
   stage using a fresh restored snapshot, with all commerce flags disabled.
3. Test signature security, real mainnet merchant wallet proof and
   independently finalized ETH/TRX payment with **separate approval for
   actual money movement**. Repeat/replay/expiry/incorrect-wallet tests.
4. Approve only editorially validated and legally distributable products.
   There are currently no active products; paid listing is a different
   operation from a healthy commerce engine.
5. After full backup and stop/go review, apply only the scoped changes
   under a controlled deployment window; check homepage, store, admin,
   checkout, entitlements and previously functional routes.
6. On any failure disable newly added routes/flags, restore **only** the
   exact changed code from private snapshots and verify site smoke tests.
   Do **not** restore an old live DB blindly if new orders/data exist;
   reconcile any writes first and obtain explicit consent for destructive
   rollback.

**Current release verdict:** NO-GO for live checkout until the remaining
wallet/payment evidence and scoped source patch pass. A passing migration
or disposable MySQL suite alone is insufficient.

# Zomorod Melal — guarded private accounting DB initialization (2026-11-01)

Scope: the isolated PHP business/accounting application at /business/. This is **not** the Django Passenger database, and not any VPS factory database.

## Invariant

Ordinary HTTP requests must open **only an existing, readable, non-symlink private SQLite DB** with the expected 13 accounting tables. They must never implicitly:
- create a replacement management.sqlite3 after disk loss or a misplaced deployment;
- create/repair tables (DDL) or re-seed the chart of accounts;
- set persistent SQLite journal mode;
- mint a new one-time first-admin secret.

A missing/invalid/incomplete DB or missing first-admin setup token fails closed. The private server error log explains why without exposing the DB or token to the browser.

## First installation, only on a clean new private directory

Run **only with local shell access on the actual cPanel account**, after validating that the private directory is owned by the account, not a symlink, and there is no prior DB/token or historical accounting data.

The PHP app's CLI entrypoint now supports:

```sh
php /home/zomorod2/.private/zomorod-business/app.php --initialize-private-db
```

This command requires an **absent** management.sqlite3 **and** absent setup.token. It exclusively creates a new SQLite file (0600), installs exactly 13 schema tables and 12 starter ledger accounts in a single transaction, then creates a 64-character one-time setup token (0600). It does **not** print the token. The first administrator uses that token in the browser and the application removes the private token after successful activation.

**Never run this initializer against the already-running Zomorod production DB.** It is deliberately one-shot and refuses any existing DB or token. Existing schema upgrades require an explicit backup, approved migration and rollback, not this initializer. If partial files remain after an error, investigate and recover; do not delete them blindly.

## Safe release prerequisites

- Read-only verification on cPanel of the actual PHP private DB path, file mode, 13-table schema, seeded entries and account inventory; no DB mutations.
- Owner-key independent offsite decryption and restore proof, not only a locally restorable encrypted artifact.
- Effective Passenger Django DB identity remains separate from PHP management.sqlite3.
- Auth/MFA, CSRF, replay/role behavior, backup/rollback and live acceptance proven.
- Integrate and rerun the pending invoice/stock atomicity patch (#1769) and POST logout patch (#1771) before any production deployment.

Test coverage: isolated real PHP HTTP server + disposable temporary SQLite and CLI install, with missing/incomplete/symlink DB refusal, no silent token creation, one-shot installer, first-admin setup and read-only GET checks. No actual site/DB connections, write operations or deployments.

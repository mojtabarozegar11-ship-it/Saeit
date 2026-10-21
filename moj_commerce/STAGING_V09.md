# MOJ Commerce v0.9 — staging admission record (2026-10-21)

**Status: read-only SSH connectivity preflight only. No staging transfer, migration,
schedule or live payment is performed by this branch.**

## Fixed boundaries

- Repository: `mojtabarozegar11-ship-it/Saeit`; source: v0.8 branch + this v0.9 preflight.
- Relay: GitHub Actions → VPS `githubops@178.239.147.150:22` →
  `zomorod2@zohal.pws-dns.net:1396` via ProxyJump.
- cPanel staging root (historically confirmed; must revalidate): `/home/zomorod2/Saeit-staging`.
- Production is **not** staging: `/home/zomorod2/Saeit` and public webroots must not be modified.
- Existing `staff-staging-release.yml` activates files in Production. **Never use it for MOJ Commerce.**
- Both SSH hosts require exact independent SHA-256 host-key fingerprint matches.
  Fail closed if unreachable, unknown, changed, or keys absent.

## Read-only verification

The dedicated `moj-commerce-v09-relay-preflight.yml` checks:

1. Authenticated VPS SSH identity and pinned VPS RSA key.
2. Independent host ed25519 fingerprint acquired through pinned VPS.
3. Authenticated cPanel account over SSH ProxyJump.
4. Presence of staging root and passive detection of staging venv/source.
5. Distinguishes existence of Production path from any write; no command mutates it.

Its job cannot claim readiness of PostgreSQL, network RPC providers, customer funds,
passenger routing, cron, signed wallet ownership or recoverable backups.

## Required gates before a later staging deployment

1. Owner-controlled isolated stage directory (suggested `Saeit-staging/moj-commerce-v09`)
   and explicit write allowlist; never copy to `Saeit`, `public_html` or Passenger root.
2. Immutable reviewed source revision; malware/secret/path traversal scan; SHA-256
   of a staged archive; no key material packaged.
3. Independent, stage-only PostgreSQL database and credentials; no use of Production DB.
4. Stage feature switches **off**: `MOJ_COMMERCE_RECEIVER_ENABLED=False`,
   `MOJ_COMMERCE_CHECKOUT_ENABLED=False`,
   `MOJ_COMMERCE_SCANNER_ENABLED=False`,
   `MOJ_COMMERCE_RECOVERY_ENABLED=False`,
   `MOJ_COMMERCE_SELF_REPAIR_ENABLED=False`.
5. A standalone Django stage configuration with no public URL or Cron binding.
   `moj_commerce.test_settings` is synthetic CI-only and must not be reused with
   actual buyer or wallet data.
6. `python -m django makemigrations moj_commerce --check --dry-run`, migrations
   only on isolated stage DB, full Django tests, PostgreSQL advisory-lock concurrency,
   and no-outbound-funds proof.
7. Verified restoration from stage backup and a tested removal/revert procedure
   **before** any paid canary.
8. Independent TRON finalized transaction sources, operator ownership proofs,
   legal/commercial review, and explicit approval before public purchase or money flow.

## Strict go/no-go

- **SSH green** means connectivity to staging is possible, not that checkout works.
- **CI green** means tested source contracts, not that blockchain payments are safe.
- Do not activate public checkout, delivery, live addresses or 24/7 scanner
  until all external gates are supported by timestamped operational receipts.

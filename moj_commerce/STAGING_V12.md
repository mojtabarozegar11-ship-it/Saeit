# MOJ Commerce v1.2 — MariaDB isolation and release evidence (2026-10-22)

## Scope and decision

**Source and private staging: verified. Production release: NO-GO.**
The existing MojPlayWin MariaDB must be reused; never create a replacement
database or repeat production migrations on this branch. No production money,
TRON broadcasts, live checkout routes, production DB writes, cron enrollment,
domain rewrites, or Passenger restart is authorized by these test receipts.

## Evidence: real MariaDB and cPanel

- [Isolated MariaDB financial acceptance 39682114048](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39682114048): 65/65 Django tests on disposable MariaDB 11.8.9; real InnoDB concurrency for scan mutex, duplicate finalized callbacks, cross-order txid replay, single wallet-address reservation, buyer idempotency, safe stale-run closure, and normal synthetic delivery. Synthetic TRON proofs; no blockchain funds or production database touched.
- [Read-only cPanel MariaDB release audit 39683666596](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39683666596): existing cPanel MySQL catalog matched a single scoped MySQL configuration URL; actual read-only SQL query succeeded; non-InnoDB BASE TABLE count 0 for that database; hosting quota measured with available capacity. No wallet, transaction, restart or site write.
- The same read-only audit **did NOT verify Passenger's effective runtime DB**; neither production nor original staging directory contained a mounted `moj_commerce/models.py` at the inspected paths. Do not claim this app is installed in live production.
- [Private non-public cPanel staged source smoke 39684178145](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39684178145): source and pinned wheelhouse checksums matched after copying to a fresh, private sandbox under `/home/zomorod2/.local/share/moj-commerce-v12-private-smoke/` (never the live docroot). New isolated Python environment installed; Django's SQLite synthetic tests finished `Ran 122 tests / OK (skipped=10)` (112 succeeded, 10 MariaDB-only checks skipped). The 10 cases were separately exercised on real disposable MariaDB in the preceding CI job. No live route or DB mutation.

## Existing release blocker: verified restoration

- [Production-backup attempt 39657480155](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39657480155) created an encrypted GPGv2 SQL archive and verified decryption, but its isolated file recovery ended `SANDBOX_FILE_RECOVERY_FAILED_NO_RELEASE`.
- Therefore **full tenant DB/files restoration and independently recoverable key custody are unproven** by these receipts. Never promote a stage test to authorization for live deployment or real customer charges.

## Required conditions before any live release

1. Confirm Passenger's actual running DATABASES mapping without exposing secrets; confirm no conflicting URLs/routes for MojPlayWin and child applications.
2. Verify full, coherent MariaDB + file/media backups, independent copy of the recovery key and successful isolated restore of both SQL and all intended site roots.
3. Compare stage-vs-live Django migrations and table names. Never run a migration on the production MariaDB as part of a test; explicit release procedure must review existing data and rollback.
4. Prove the actual independently configured TRON finalized-body/receipt verification, merchant address signature and issuer payment data are correctly bound to a locked invoice. Synthetic fixtures or a successful SELECT 1 do not constitute a live payment.
5. Preserve all existing public site/subsite routing and appearance; activate feature flags and a private acceptance purchase only after gates 1–4 and explicit operator acceptance.
6. Validate rollback without changing the public site, then perform a limited real-money end-to-end checkout only after owner authorization and suitable precautions.

There are no secrets in this document, and no release performed.

## 22 October — isolated recovery of every regular file, unsafe links quarantined

- [Pass: release preflight + authenticated archive and isolated file extraction, run 39686843435](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39686843435): nine synthetic safety/unit tests passed. An existing GPGv2 `files` archive was authenticated and streamed twice via pinned GitHub→VPS SSH into an ephemeral runner; no archive, secrets or production data published as artifacts.
- Metadata classified 23,567 regular files, 2,076 directories, zero duplicate/escaping file paths, and **exactly three symlinks with absolute targets**.
- Fresh isolated file restoration wrote **all 23,567 regular files**, with **847,868,787 bytes** restored and 2,076 directories. It did **not** materialize or follow the three absolute links. The temporary runner directory was scheduled for cleanup by EXIT trap.
- Because those three links remain unresolved, the runner itself records `absolute_links_quarantined=3`, `restore_complete=false`, `release_permitted=false`. Do not call this a complete functional/tenant restore.
- A separate [read-only authenticated archive classification run 39686215199](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39686215199) had independently identified the same three absolute links, explaining the earlier fail-closed file-restoration rejection.
- Source-only Passenger inventory found .htaccess directives and WSGI entrypoints, but **could not prove which running Passenger process/DB binding is active**; no MOJ Commerce public route mount observed in inspected source. Do not infer release authorization from config-file presence.
- Off-host recovery key custody and independent child-site backup coverage remain unverified. No production modifications, payment broadcasts or database writes.

Next: classify the three symlink targets privately (no target strings in logs), reconstruct runtime dependencies within a separate recovery sandbox, verify site-level recovery and independent key custody, and then prove effective Passenger→MariaDB runtime mapping before considering a real TRX purchase.

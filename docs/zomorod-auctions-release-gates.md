# Zomorod Melal auction route: release gate and rollback (2026-10-31)

State: **HOLD (private-stage only)**. This document is not a live-deployment approval.

## Verified facts

- Draft PR #1726 holds the standalone auction source `content/zomorod-business/auctions.php`, SHA-pinned test source commit `8a93511adbcddb6b228b93d9c5d46064b8ea1a09`.
- On cPanel, that exact source is already staged privately as `/home/zomorod2/.backups/zomorod-auctions-staged/8a93511adbcddb6b228b93d9c5d46064b8ea1a09/index.php`, with SHA-256 match and successful PHP 8.3 lint: Actions #41226225337.
- Site production web SAPI is LiteSpeed PHP 8.2.35, without `fileinfo`: Actions #41226775331.
- A **temporary isolated subdirectory** with `AddHandler application/x-httpd-ea-php83 .php` executed PHP 8.3.36 and loaded SQLite3, fileinfo, and sessions, while the global site PHP stayed at 8.2.35: Actions #41226889499. The temporary files were removed.
- The precise tested handler is versioned as `content/zomorod-business/auctions.htaccess` and must be placed **only** at `/public_html/business/auctions/.htaccess` when release is authorized.
- Existing `/home/zomorod2/.private/zomorod-business/app.php`, `management.sqlite3`, and `/public_html/business/index.php` are host-specific and must not be replaced.

## Hard gates before an additive production route

1. Identify the actual backup destination and a timestamped, encrypted, off-host copy of the **office** `management.sqlite3` and required website code. Do not use a factory backup as office evidence.
2. Prove restoration of that exact backup to a *separate isolated location*, inspect SQLite `PRAGMA integrity_check`, essential tables, and retain a redacted restoration receipt (hash, date, location type, result). Do not log the private database contents or credentials.
3. Confirm the staged source SHA-256 still matches the approved GitHub source; verify there is no existing `/business/auctions` directory or symlink, and that the parent permissions are safe.
4. Deploy only two files (`index.php`, `.htaccess`) by atomic rename of a newly created same-filesystem temporary directory. No overwrite, migration, rewrite of app.php, modification of master DB, or domain-wide PHP version change.
5. From unauthenticated HTTPS verify the auction route returns access denied rather than displaying private data. Then conduct *legitimate signed-in* tests for read-only user, operator, finance reviewer, executive reviewer, separated approvals, PDF/JPEG/PNG upload and RBAC, independent receipt, and audit trail.
6. Disable or quarantine new route on any failure. Preserve any new auction SQLite file and uploaded documents for forensic review; never delete the master DB or roll back other modules.

## Release stop conditions

- Off-host backup is not verified by an actual isolated restore.
- Per-route PHP 8.3, SQLite3, fileinfo or sessions fail on **actual** live HTTPS after installation.
- Existing auction route already exists; symlinks or path ownership differ from expected.
- Real role-based authenticated tests are missing or show privilege escalation.
- Public HTTP response exposes a stack trace, private document, unauthorized record or successful anonymous action.

## Scope and receipts

- The feature is an **internal auction opportunities/approvals register**. It never places bids, pays deposits, or sends outside messages.
- Main business ERP management scope remains Issue #1725, auction feature PR #1726.
- Evidence: [host preflight](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41226089107), [private stage](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41226225337), [web runtime](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41226775331), [scoped PHP 8.3](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41226889499).

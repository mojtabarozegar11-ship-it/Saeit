# Zomorod Melal ERP — integrated V7 offline QA handoff

**State: DEVELOPMENT ONLY. DO NOT DEPLOY OR CHANGE LIVE DATA.**

This isolated integration branch combines the unified V7 agriculture/industry, finance, accounting-period and payroll modules with the separate treasury proposal/review and CLI-only owner credential rotation branches. It preserves the live site's existing appearance and does not operate on live cPanel, banking, personal credentials, factory or another domain.

## Verification scope

- The unified offline runner fail-closes if any required PHP/PDO_SQLite suite fails or cannot run; now includes the treasury synthetic SQL regression, authenticated login/CSRF/dual-review web flow, and synthetic owner password-rotation regression.
- The web-flow test's disposable private app fixture includes industry, finance, period, treasury and payroll modules so missing dependencies cannot be silently skipped.
- PHP 8.2 and 8.3 must both pass on a fresh GitHub Actions run from the integrated commit; previous branch CI does not certify this new merge.
- The source-only archive has an explicit manifest, hashes and verification, and is not a release payload for overwriting the live app.php.

## Mandatory release blockers

1. Reconcile the exact latest conversation-only V7 full source bundle against this branch, rather than assume identical contents.
2. Read-only inventory and module-by-module diff against live server-only /business/ PHP extensions; no wholesale app.php replacement.
3. Confirm private runtime PHP/PDO_SQLite, schema and file permissions. Restore an encrypted off-host backup to an isolated stage and prove rollback before any migration or change.
4. Validate statutory payroll, tax, insurance, financial reporting, industry/LIMS/MES and the authenticated command signer against applicable requirements.
5. Private owner staging login acceptance with a new strong password from a secure input path, not a chat transcript; no credential, hash or token in GitHub.
6. No bank transfer, public posting, external message, payment or recurring task is enabled by this code.

Release stage remains **CODE / NOT MERGED TO MAIN / NOT DEPLOYED / NO LIVE ACCEPTANCE**.

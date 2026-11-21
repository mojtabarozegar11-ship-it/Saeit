# Zomorod Melal — payroll offline proposal module

**Release classification:** PRIVATE SOURCE / TESTED OFFLINE / NOT A PAYROLL PROVIDER OR PRODUCTION BANKING SYSTEM.

## Implemented and tested

- Propose one payroll calculation per UTC/Gregorian calendar month, with exact integer minor units.
- Up to 100 unique employee references per period in the storage engine; current UI supports up to eight employees per entry.
- Explicit base pay, manually entered additions and deductions, gross and net totals.
- Bound deductions to earnings, reject invalid amounts and duplicate period/request IDs.
- Immutable payroll lines, append-only audit events, no deletion of a period.
- Distinct reviewer required for submitted payroll approval.
- SQLite trigger rejects illegal state transitions and direct self-approval.
- Separate 0600 private SQLite sidecar database, no company ledger, no external payroll.
- Authenticated private ERP nav route and POST actions with existing session, CSRF and role permissions.
- Real synthetic web sign-in and dual-admin approval tests plus unit regression.

## Not implemented — financial and legal safety boundaries

- Legal employment terms, statutory overtime or minimum wage calculation.
- Payroll tax withholding, social insurance, payslip compliance, salary settlement or bank transfers.
- Timesheets, benefits, payroll correction/reversal, encrypted PII fields, payroll export and ledger posting.
- Country-specific statutory rules, 100+ employees in one UI session, integration with actual employee roster.
- Production owner acceptance and independent data privacy audit.

**No payroll period approval transfers funds or changes ledger entries.**

## Safe integration instructions

1. Do not overwrite the existing live `app.php`; it contains server-only features not present in the repository.
2. Require exact live source fingerprint, backups of private code and a verified restorable SQLite snapshot.
3. Install only `payroll_control.php` and `payroll_ui.php` under the existing private company directory outside public_html. Enforce 0600.
4. Apply only unique-anchored require, route, nav and POST-action changes matching this branch's diff.
5. Run PHP 8.2/8.3 lint, PDO SQLite QA and separate staged login/CSRF/owner-role tests.
6. Verify the public site did not change, unauthorized users see only the login, and accounting/payments remain unmodified.
7. Do not enable any hourly job before company system completion and owner acceptance.

## Acceptance boundary

The module has an **offline code and regression test scope**. It is not proof that all 24 company ERP areas have complete coding, that tax/payroll is legally correct, or that ChatGPT commands can reach live cPanel.

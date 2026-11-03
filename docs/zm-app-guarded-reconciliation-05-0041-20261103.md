# ZM management desk: reconciled app source and guarded promotion (05-0041)

Date: 2026-11-03. Scope: `zomorodmelal.ir/business/` only. No storefront or factory changes.

## Recorded source change
- Previous live app at `/home/zomorod2/.private/zomorod-business/app.php`: SHA-256 `ad9c80fc1bcff01c53cb58acabd088890e9f1dd0b7e3c38c95bd1ff4d67f27a7`.
- Live source snapshot: `content/zomorod-business/app.production-20261103.php` (one extra final LF only).
- Previous feature-branch `content/zomorod-business/app.php` diverged at **49** line-oriented edit regions.
- Reconciled, syntactically valid source is now the feature-branch `content/zomorod-business/app.php`, with an identical independent candidate `app.reconciled-candidate-20261103.php`.
- This change is **GitHub development source only**; no production app deployment was attempted.

## Preservation and reconciliation
The reconciled branch app preserves the live workflow, project-control, document-linkage, documented project approval, milestones, assignments, operations, payroll, financial-period, finance-audit, report, and command-center routes. It preserves the prohibition on generic legacy bank account 1010 payment postings and restricts newly created projects to planned or paused states.

The branch's accounting protections were incorporated: CSRF-protected POST logout; session role refresh after a role change; reject non-scalar POST fields; positive integer validation; explicit private-database initialization (no silent recreation or schema writes on routine HTTP requests); journal reversal only for independent manual entries; stronger purchase classification and party validation; transactionally consistent inventory changes; field-length boundaries; audited creation; user deactivation/role editing with self-lockout guard; controlled error buffering; and the read-only approval-register view.

The implementation retains the live accounting-period check in journal posting and calls the period schema initializer only in the explicit CLI installer. This last bootstrapping path has **not** been end-to-end accepted on a fresh authorized server installation.

## Deployment gate attached to an existing app writer
The real historical GitHub Actions flow `.github/workflows/zm-banking-nav-live-20261102.yml` now ships the read-only `scripts/zm_production_app_guard.py` plus the stored production snapshot to the private stage and invokes the guard **after calculating its proposed patched candidate but before publishing it over live `app.php`**. The guard requires the exact verified live digest, equivalent reference bytes (allowing only the known final LF), and an equivalent candidate. Any changed candidate needs a separate reviewed reconciliation release path.

Workflow attempt [41570357557](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41570357557) failed, without publishing the app. A subsequent **read-only** host inspection showed the historical one-hunk patch cannot apply to the already evolved live source (`Hunk #1 FAILED at 132`). The staged guard was independently executed against the untouched source and returned **PASS**, with the live, snapshot and candidate digests recorded. The failed run is **not** a successful end-to-end production release and is **not** evidence that the guard intercepted the historical patch inside that run. The historical workflow must not be treated as the new unified release vehicle.

## Read-only host acceptance evidence
- Production `app.php` digest remains `ad9c80fc1bcff01c53cb58acabd088890e9f1dd0b7e3c38c95bd1ff4d67f27a7`; live app and DB permissions are `0600`.
- Main `management.sqlite3`: 26 tables, `PRAGMA quick_check=ok`, zero foreign-key violations, 194 projects and one user.
- Zero project links, zero project-approval cases/events, zero project milestones/assignments, zero journal entries and zero invoice payments. One existing document, without an evidenced project link, must not be assigned on guesswork.
- Anonymous `/business/` returned 200 (login shell only). This is not authenticated functionality acceptance.
- Reconciled branch candidate passed PHP 8.2 syntax check using a read-only stream on the authorized host. No real owner credentials were read, exported or used.

## Remaining release blockers
1. Independently check action/role behavior, all management forms, accounting-period transition, governance review, reports and document links with an authorized real owner session.
2. Verify the merged candidate in a permission-isolated, non-writing acceptance environment against the existing schema, without fake official records or financial events. No false acceptance claims from lint alone.
3. Create a **new** explicit, digest-pinned reconciliation release workflow with pre-image backup, candidate review, database snapshot consistency, forward and reverse migrations (if any), and automatic rollback; retire or disable old one-hunk replay routes after owner-approved release.
4. Do not allow high-impact governance clearance with the only current admin; enroll a real independent reviewer through authorized policy.
5. Link real verified project documentation and responsibilities only after source IDs and written evidence are available.

Decision: `APP_SOURCE_RECONCILED_IN_BRANCH=yes`; `PRODUCTION_APP_DEPLOYED=no`; `OWNER_AUTHENTICATED_ACCEPTANCE=pending`; `FINANCIAL_RECORDS_MODIFIED=no`.

# Zomorod Melal ERP — source reconciliation and acceptance status
Date: 2026-11-03. Scope: management and accounting only; no factory or storefront changes.

## Production source preserved
- Current production private file: `/home/zomorod2/.private/zomorod-business/app.php`.
- Production source SHA-256: `ad9c80fc1bcff01c53cb58acabd088890e9f1dd0b7e3c38c95bd1ff4d67f27a7`.
- GitHub production mirror: `content/zomorod-business/app.production-20261103.php` in `feature/zm-bank-ledger-20261102`.
- Mirror SHA-256: `7a8b2ab1dde07317c084646e4005ac843011821903f65b12297d283ee69412bd`.
- Byte audit: mirror matches **every production byte except exactly one extra final newline** introduced while archiving. Do not claim bitwise identity of the two SHA-256 values.
- Original branch `content/zomorod-business/app.php` SHA-256 as copied to the server for comparison: `ef89f6c0eea36f5d5a697c402a495413183316417f5fe33ebc7086f778273f91`. It differs materially in roughly 49 code edit blocks. It contains additional input validation, journal reversal, administrative controls and a different DB initialization implementation; production includes workflows, business management modules, banking redirection, finance-period controls and project/governance integrations missing from the older branch edition. Neither source may be blindly overwritten by the other.

## Deployment safety guard
- Read-only guard committed as `scripts/zm_production_app_guard.py`.
- The guard checks the **live file against the captured expected SHA-256**, matches the production mirror with allowance only for a single terminal LF, and optionally checks a release candidate file.
- Tested against current production: PASS, return code 0.
- Tested against the legacy branch's `app.php` as a proposed candidate: BLOCK, return code 2.
- This tool does **not** automatically intercept every existing GitHub Actions deployment; a future deploy workflow must explicitly invoke the guard before it uploads/replaces `app.php`. No deployment or merge was attempted in this release. An additional backend source comparison and reviewed merge of both application editions are required before using the branch app as a production release.

## Governance authorization tightened
- Live `project_governance.php` now joins the reviewer with the `users` table and requires a presently active `admin` reviewer for previously approved execution clearance. As before, the reviewer must differ from the requester; the linked document's title/body digest and project link must match.
- A deactivated reviewer or reviewer stripped of admin privilege stops conferring execution permission.
- The isolated private-memory governance suite expanded from 37 to **40 passed checks**, including revocation on reviewer deactivation and demotion, and restoration of eligibility after role recovery.
- GitHub: `content/zomorod-business/project_governance.php` and `tests/test_zm_project_governance.php`.
- Only **one real active admin account** exists. No fake second reviewer was created. Execution approvals that require independent review remain pending until an actual authorized second reviewer exists.

## Acceptance limits and cleanup
- A secure, isolated shadow copy of the live application and its database was constructed for internal UI checks with disposable accounts. A reliable end-to-end UI acceptance result was **not** produced. The shadow directory was removed after the attempted checks. Production sessions and credentials were not used.
- Anonymous requests to `/business/`, `?page=project_governance`, and `?page=project_portfolio` returned 200 but displayed login; this is not authenticated application acceptance.
- Seven live PHP modules passed lint, production SQLite `quick_check=ok`, foreign-key errors=0, and the 40 isolated governance checks passed.
- Production state: 194 projects; zero project approval cases, approval events, linked project documents, milestones, journal entries and invoice payments.
- Restricted copies and a reference of the pre-change production app were retained in `/home/zomorod2/.backups/zm-main-app-reconciliation-20261103/` with private permissions.
- **Remaining priority:** complete a reviewed merge of the different application editions; attach the source guard to the actual GitHub Actions production promotion route; perform authorized owner-session acceptance; enroll a genuine second independent reviewer if required by company policy. Do not bypass two-person approval to meet a completion metric.

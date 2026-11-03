# Zomorod business management desk — live module identity manifest

Date: 2026-11-03 (UTC). Scope: `zomorodmelal.ir/business/` only.

The production `app.php` candidate at `content/zomorod-business/app.php` is **not yet deployed**. The release action `.github/workflows/zm-business-app-reconciliation-release-20261103.yml` checks the *live* PHP dependency identities before any publication. The live `app.php` SHA-256 baseline is `ad9c80fc1bcff01c53cb58acabd088890e9f1dd0b7e3c38c95bd1ff4d67f27a7`; the reviewed candidate SHA-256 is `2ed9274affa87f3e9c51f7dff0c72d7461118c7aca0ae0ab732b1c81cbfd6005`.

## Actual code dependency inventory

Git blob IDs are content fingerprints, **not proof of authorization or successful user acceptance**. Do not publish the private-only sources to a public repository without separate security review.

| Production module | Status relative to feature branch | Production Git blob | Branch Git blob |
| --- | --- | --- | --- |
| workflow_desk.php | identical | `8eb08aace27c7f259cf6bd4ed7922b60dda1fb8c` | identical |
| project_control.php | identical | `288ad642c737f43c9c605a472bbcec97940bdef7` | identical |
| project_integrations.php | identical | `290ebef529145c91a53a2bed8d8465332c8e84e9` | identical |
| project_governance.php | identical | `727cb86b21f94097591835b8249d37fa950f2b14` | identical |
| project_ops.php | identical | `cd39cfdc69a347891661eb2384be41d89207f1be` | identical |
| project_portfolio.php | identical | `f7d2969a37affbe95bfb59345f0df9cc4e01cee5` | identical |
| industry_operations.php | private-only | `c0ea47deb93a981108eb7dcc6340533af1258b87` | absent |
| finance_audit.php | private-only | `b248207cbd8988e8c6a318e7e9330dda42871841` | absent |
| payroll_control.php | private-only | `76ce2ed38588075cf9e5b257dd43c07d73295db7` | absent |
| payroll_ui.php | private-only | `47261ea0632a2e2d6b41f7fb64c71cfc207dd04a` | absent |
| period_controls.php | private-only | `ef17c766336a9b4da00872588c239a05290a00a6` | absent |
| site_agents.php | private-only | `e0e749703ba1f97f7879ecc65e32ad7ffcfcc54d` | absent |
| command_center.php | private-only | `10287639b126aa811c1c9585767404923795d74e` | absent |
| site_store.php | live differs | `a7e85d081bec2c83982de5a80480125801e78fb1` | `5bc43c8363bfc0fa0ee6ee4ff50462cd6cdc474e` |
| insights.php | live differs | `b113767f4564dc99a4703f2cfcbee37a58f03d06` | `288e967cd9d7a6647ffa06f8ac6d8b61514b2e06` |
| chatgpt_reports.php | live differs | `c668d5c12109f62c4b371823b1711860f63e4e30` | `ba8aa31e50896fca02808db8d58dee9384c4b018` |

The direct cPanel read-only audit found the PHP modules present, without symlinks and syntax-clean. All seven critical exports (`zmGovHandle`, `zmPiRender`, `zmOpsAssignmentsDesk`, `zmPeriodGuard`, `zmAgentHandle`, `zmCcRender`, `zmBusinessChatgptReports`) were found in their intended production files.

## Release invariants

1. Verify all sixteen actual production Git blobs and seven required PHP entrypoints before publishing the candidate `app.php`; fail closed upon drift.
2. Never replace any live module from the divergent branch merely because a same-named file exists in GitHub.
3. Do not merge all of `feature/zm-bank-ledger-20261102` into `main`: the branches were 426 ahead/102 behind at review time and include unrelated changes.
4. The dedicated publication workflow creates owner-only backups, uses SQLite online backup, compares the baseline hash, and retains code rollback. Its `publish` path requires a private SHA approval secret and has **not** been executed.
5. Do not assert authenticated role/form acceptance until a real authorized manager session has been used; anonymous login-page checks alone are insufficient.
6. No fabricated project links, ledger entries, payments, appointments, employees or independent reviewers.

Evidence: preflight GitHub Actions run [41585778062](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41585778062) succeeded after the module-identity gate was added.

## Live app release route ownership (2026-11-03)

An additional read-only review identified historical workflows that could write to the live `app.php` only when their own obsolete files were changed on specific feature branches. To avoid accidental execution of conflicting patches, their automatic `push` triggers have been removed; they now require an explicit manual `workflow_dispatch` with `historical_patch_acknowledged=true` and retain their preexisting remote checks. This manual switch **does not** constitute publication approval, a successful acceptance test, or permission to bypass the dedicated reconciled release.

| Historical workflow | Historical branch | Retirement commit |
| --- | --- | --- |
| `zm-banking-nav-live-20261102.yml` | `feature/zm-bank-ledger-20261102` | `be38fead3a926d63a4de4cd5a25c816e9b69f013` |
| `zm-business-rbac-kpi-guarded-release-20261102.yml` | `feature/zm-business-php-persian-reports-20261102` | `6685dcc5eb81a92fff6b5e25026e0c6d0e23be70` |
| `zm-business-php-chatgpt-report-guarded-release-20261102.yml` | `feature/zm-business-php-chatgpt-reports-20261102` | `6a1d9750dfec60b65992454402b233beb2f21e00` |

For the current management desk, use `.github/workflows/zm-business-app-reconciliation-release-20261103.yml`, with its read-only push preflight and **separately authorized**, hash-verified `workflow_dispatch: mode=publish` path. The first-install `zomorod-business-release.yml` on `main` has an existing-directory refusal and is not a route for overwriting this live installation.

### Authenticity boundary for project–document references

Production currently has a real project whose full title (`projects.id=39`) appears in `documents.id=1` (the Foundation properties/employment dossier). `zm_project_links` has no rows. This is **only a candidate** for a legitimate reference: the application must record any link using the existing `project_integrations.php` authorized actor, role, CSRF, transaction and audit flow. Do not insert directly into SQLite, invent a current authenticated actor, or count a candidate as an approved project link. Financial/accounting data are unchanged.

## Manual dispatch entrypoint and post-publication gate (2026-11-03, cycle 05-0049)

GitHub Actions `workflow_dispatch` requires the workflow to exist on the **default branch**. The reviewed publication workflow existed only on `feature/zm-bank-ledger-20261102`, so no manual branch-selector launch was available through the default-branch workflow list. An inert default-branch anchor was created at the **same path** `.github/workflows/zm-business-app-reconciliation-release-20261103.yml` in `main` (commit `5c2b64b2b96825d0a8d9444d9ebd3c964e8b3fa7`). This anchor contains no SSH secrets and always fails with instructions if selected on `main`.

Authorized release sequence:

1. In Actions select **ZM reconciled business app guarded promotion**, then select branch `feature/zm-bank-ledger-20261102` (not `main`). `mode=preflight` is read-only.
2. Production publication requires `mode=publish` **and** the separately provisioned repository secret `ZM_APP_RELEASE_APPROVED_SHA256`, equal to the reviewed candidate digest `2ed9274affa87f3e9c51f7dff0c72d7461118c7aca0ae0ab732b1c81cbfd6005`. The secret value is not stored or retrieved by this document.
3. The feature workflow checks immutable source, private module Git blobs, cPanel SSH host pins, DB schema/integrity and production `app.php` baseline; it makes an owner-only code and SQLite backup before its guarded atomic swap.
4. After publishing, it must verify all **14 anonymous protected routes** still display the login form with no management navigation or data table, plus a read-only `PRAGMA quick_check` and foreign-key check. Failure triggers code rollback. This is only an *anonymous access gate*, **not authenticated acceptance**.
5. The sole current live admin's authenticated acceptance of management, accounting, projects, calendar, reports and role permissions remains outstanding. Do not invent a second reviewer, approve real transactions or claim completion solely from a green CI run.

Source: [GitHub's workflow_dispatch default-branch prerequisite](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onworkflow_dispatch).

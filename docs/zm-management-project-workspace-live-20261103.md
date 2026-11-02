# Zomorod Melal: management and accounting project desk — live release, 2026-11-03

## Focus (explicit owner scope)
The task is to complete the **management and accounting workspace** at `https://zomorodmelal.ir/business/`. No store gateway, factory restart, product launch, payment, hiring or financial commitment was attempted in this change.

## Live changes
- Installed private `project_control.php` beside `app.php` within `~/.private/zomorod-business/` (mode 0600).
- Integrated the module with authenticated POST handlers `project_transition` and `project_update` inside the production `app.php`, preserving existing roles and CSRF check.
- Replaced the old projects listing with a management project workspace showing status metrics, paginated records, internal decisions, blockers, an append-only progress history and an append-only status transition history.
- Row-specific project state forms embed the expected state to prevent concurrent stale updates. Legal transitions only: planned→active/paused, active→paused/done, paused→planned/active; done is terminal. Changes require a documented reason, live admin/manager authorization and a transaction-bound audit event.
- Added management-project status counts and links to project desk, workflow desk and ChatGPT cycle reports to the live dashboard.
- New project creation permits `planned` or `paused` only; administrative status never proves physical activity, hiring, payment, or employment.
- Created `zm_project_events` and `zm_project_updates` in production `management.sqlite3` with user and project foreign keys, plus indexes. No historical project record was edited, activated or closed.
- The existing `app.php` differs from GitHub; **do not overwrite production with an outdated copy**. Patch it surgically. Necessary integration points: (1) optional require `project_control.php`, (2) POST branch to `zmPmSchema($db); zmPmHandle($db,$action)`, (3) GET projects renders `zmPmRender($db)`, (4) dashboard metrics query by project state. New source module is versioned under `content/zomorod-business/project_control.php`.

## Acceptance evidence
- Live accounting DB immediately after install: 194 project records (146 planned, 48 paused, 0 active, 0 done); 0 project transition events, 0 project progress updates; 0 invoice payments or journal entries.
- An isolated PHP/SQLite memory regression suite passed **18** checks, including admin and manager state transitions, stale-update rejection, invalid lifecycle rejection, viewer read-only restriction, progress/blocker updates, audit events, append-only history, page render, DB integrity and foreign keys.
- PHP syntax checks: `app.php`, `project_control.php`, `finance_audit.php`, `workflow_desk.php`, `period_controls.php`, `command_center.php` all clean.
- Site responds HTTP 200 at `/business/` and `/?page=projects`. **These 200 codes represent the login page for a visitor without a session; they do not prove authenticated browser rendering.** Authenticated UI acceptance with a real owner session is still outstanding.
- A consistent SQLite copy and previous PHP source are held in a restricted backup folder `/home/zomorod2/.backups/zm-management-project-controls-20261103/` with mode 0600 for files; no active database was restored or rolled back.
- No third-party money transfer, invoice, employment, physical operations or project-state modification occurred.

## Further gaps in overall ERP readiness
End-to-end authenticated owner/manager usability, user access administration and MFA, calendaring with actual action tracking, immutable cross-module action evidence, accounting period-end acceptance and production recovery disaster drills are not yet established. None should be claimed completed based solely on module installation and isolated tests.

## Operator warning
Projects imported from development proposals are **administrative entries**, not evidence of real funded/started projects. Any conversion to actual business activity must be authorized and independently evidenced. Never mark 194 registered projects as active merely to populate dashboards.

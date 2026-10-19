# Zomorod Melal — Private Company Office / ERP v1

**Current status:** Developed only in \`feature/zomorod-private-erp-20261017\`,
independent of draft PR #400 and the existing public website.
Do not deploy until the existing LiteSpeed/Passenger HTTP 503 defect is repaired,
full production backup/rollback tested and the private security gate passes.

## Navigation
- \`/company/office/login/\` — Django username/password with CSRF and HTTPS checks.
- \`/company/office/\` — staff-only company management dashboard.
- \`/company/office/finance/\` — posted double-entry totals grouped by unit/currency.
- \`/company/office/inventory/\` — confirmed stock balances and reorder indicators.
- \`/company/office/tasks/\` + \`/tasks/new/\` — work delegation and follow-up.
- \`/company/office/letters/\` + \`/letters/new/\` — correspondence.
- \`/admin/enterprise_portal/\` — authorized native Django administration of
  company units, ledger accounts, journal entries/lines, inventory, partners,
  contracts/invoices, meetings, budgets, projects, and fixed assets.

## Accounts and permissions
No password, username, API key or financial data is built into code.
The owner may provision a username and strong password using Django
\`createsuperuser\` in a secure console **after** server repairs. Do not paste
passwords in this chat or commit credentials to GitHub.
Ordinary staff require \`is_active\`, \`is_staff\`, and
\`enterprise_portal.view_businessunit\` to enter the private workspace.
Assign add/view/change/delete permissions per Django model. Confidential
correspondence additionally uses
\`enterprise_portal.view_confidential_letters\`; ordinary employees see
restricted letters only when creator or recipient.

## Accounting and business limitations
Double-entry journals can be posted only when positive and balanced with
at least two valid lines in the same unit and currency. Posted journal rows
are not editable in the ordinary model/admin workflow; revisions require
new reversing entries. Inventory cannot confirm more outgoing stock than the
confirmed on-hand amount. Actions append internal AuditEvent rows.
Cross-currency transactions are **not** auto-converted or summed.
Sales/purchase/quotation/contract records are tracking documents; they do
**not** automatically pay, settle, bill, create tax invoices, or book ledger
entries. Invoices and audit logs are not legal financial statements.
Tax, periods, inventory costing, bank reconciliation, payroll and proper
local legal accounting standards require separately validated follow-up work.

## Security and safe rollout prerequisites
- Restore LiteSpeed/Passenger integration for /admin/login/ and
  /api/health/, which still return HTTP 503 on production as of 17 Oct 2026.
- Back up production database and uploaded files; test rollback. Apply **only
  additive** reviewed migrations. Never wipe/reseed production.
- Confirm trusted HTTPS reverse proxy; set
  \`SESSION_COOKIE_SECURE=True\`, \`CSRF_COOKIE_SECURE=True\`,
  \`SESSION_COOKIE_HTTPONLY=True\`, and session timeout appropriate for
  finance, after compatibility tests. Enable MFA centrally and durable
  login rate-limiting and alerts before handling real company finances.
- Run \`python manage.py makemigrations --check --dry-run\`,
  \`python manage.py check\`, \`python manage.py migrate --plan\` and
  \`python manage.py test enterprise_portal\` in staging.
- Confirm preexisting URLs /, /company/, /about/, /mohammad/,
  /ghanadi/, /amozeshgah/, /farnaz/, products and payment flows remain
  intact. Publish only after the entire protected-site release gate passes.

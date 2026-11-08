# Company continuity worker — management and accounting desk

Status: implementation in code, **not evidence of production deployment**.

## What runs without a human session

`python manage.py continuity_cycle --actor=EXISTING_STAFF_USERNAME --apply`

This reads the same database as the Django management desk, checks the five
operational evidence streams A–E, follows up overdue work, and detects posted
accounting journal entries whose debits and credits do not balance. It creates
or reopens a *single* internal WorkItem for each ongoing condition and closes
only its own WorkItems when that condition clears. Each transition is logged to
`LedgerAuditEvent`. Repeated runs do not create duplicate reports or tasks.

Use `python manage.py continuity_cycle` first to produce a read-only JSON
snapshot. For unattended operation, run the `--apply` command every 60 minutes
with the site's existing Python virtualenv through **cPanel Cron Jobs or a
systemd timer on the server with DB access**, using the existing authorized
staff account name. Do not depend on GitHub Actions. Install only after the
production database and backups are verified; keep one scheduler per database.

The staff-only, read-only endpoint is:

`/staff/command-center/api/continuity/`

## What the worker deliberately cannot do

- It **does not** send email/tickets/SMS, place trades, transfer funds, publish,
  approve requests, change passwords, edit accounting journal entries, or use
  paid LLM APIs.
- A CycleReport only establishes that the action was *recorded* with an evidence
  field. It does **not** prove revenue, customer delivery, or commercial launch.
- The worker does not have a live ChatGPT conversation or OAuth session and
  cannot independently call ChatGPT Plus. Existing ChatGPT scheduled tasks may
  still review the staff dashboard when a valid session and tool access exist,
  but tasks are not a substitute for the persistent server scheduler.
- Suspicious/missing receipts remain flagged; sensitive owner decisions remain
  pending and cannot be silently approved.

## Safe acceptance checklist

1. Verify production backups and confirm the correct database/service account.
2. Run read-only mode; inspect `open_conditions`, `streams`, and journal counts.
3. Run migrations as appropriate (this feature adds no database fields).
4. Schedule exactly one `--apply` process per database at hourly intervals.
5. Verify the staff endpoint, new WorkItems and their corresponding audit events.
6. Verify a second run creates no duplicate tickets and that a genuine fresh
   evidence record closes only the matching issue.
7. Verify zero outgoing messages, expenses, financial postings and approvals.

No credentials, account tokens or user private information should be committed
to the repository. This feature cannot promise any amount of revenue.

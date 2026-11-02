# Zomorod Melal Business OS — one-pass integration candidate (2026-11-01)

**Status: SOURCE INTEGRATED FOR REVIEW ONLY. RELEASE BLOCKED.**

This branch combines the pre-existing, still-draft Zomorod office stack with:
- Unit-scoped executive dashboard and source-permission-bound specialist reporting.
- Persian/English conservative command routing; immutable MasterCommand receipts.
- Smart calendar, task workflow and opt-in follow-up creation.
- Private project register and audited **idea** intake from C-01.
- Existing messaging/marketing models with outbound dispatch default OFF.

It does not activate the VPS product factory, send messages, purchase ads,
post accounting entries, create payments, change public children/subsites, or
modify live SQLite/MariaDB.

## Code provenance
- Base: PR #1757, exact head d79e7713ee7d268dc5f8875d742b9e22be0da45d.
- Project-register files: PR #1756, exact head c066f49a5b0df2e5d010f46820ea2e7693a79323.
- Combined unit-scoped Django test workflow, exact-head checkout, and a conservative
  generic cPanel deploy preflight: **migrate --check**, never migrate --noinput.
- The production PHP /business/ ERP V7 is a separate running system, with
  a verified post-release app digest (see PR #1678) and host-only code not
  wholly represented by GitHub. Do not overwrite it from a stale source snapshot.

## Why generic deployment must stop
The previous deploy/cpanel_deploy.sh invoked migrate --noinput before production_gate.
The updated generic deployment refuses pending migrations. If schema changes are
needed, prepare a separate exact-source, owner-authorized private migration release
with independent off-host complete restoration and rollback receipts. Never simply
replace --check with --noinput.

## Single-cutover critical acceptance contract
No merge, public routing, migrations, cron, worker or live changes until ALL gates
below are independently witnessed for the SAME immutable candidate SHA:

1. Current main reconciliation: check the 44 commits that were not in the stacked
   feature branch; resolve conflicts without overwriting public site/subsites.
2. Source/runtime: match inspected source, actual Passenger WSGI path,
   interpreter, effective DB engine/host/name fingerprint (redacted).
3. Finance boundary: designate PHP management.sqlite3 as the ledger of record
   unless an explicit reconciled migration is accepted; no dual posting.
   Verify all-currency trial balances, financial closing, party subledgers,
   stock valuation, payroll and cash receipts with no duplicate/missing IDs.
4. Recoverability: independent encrypted off-host *code+effective DB* snapshot;
   full isolated restore including SQLite WAL, BLOBs/attachments and user roles;
   reconciled SHA checks and a rehearsed exact rollback cutover.
5. Security: authenticated browser tests for PHP and Django entrypoints,
   TLS, MFA (including PHP desk, if required), session revocation, login
   throttling, CSRF, cross-unit access, staff separation of duties.
6. Acceptance: actual owner-approved mobile/desktop navigation and read/write
   role flows on isolated stage, with no real funds, invoices or outbound sends.
7. Automation: no external cron or dispatch until separately authorized
   credentials, opt-in, idempotent receipts, bounded worker configuration,
   monitoring/alerts and a kill switch are verified.
8. Release: explicitly documented irreversible risks, migration order,
   source SHA, deployment and rollback timeline, and independent approval.

A green isolated Django CI means *code tests only*, not production readiness.

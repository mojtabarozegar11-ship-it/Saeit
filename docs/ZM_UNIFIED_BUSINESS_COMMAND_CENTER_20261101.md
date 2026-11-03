# Zomorod Melal — unified private business command center
Release candidate: `integration/zm-unified-business-command-center-20261101`  
Date: 2026-11-01 · Scope: **zomorodmelal.ir only** · Status: **STAGED / NOT LIVE**

## What is bundled

| Domain | Source | Capability / safety boundary |
|---|---|---|
| Private entry and dashboard | `enterprise_portal/` | Staff-only HTTPS entry, sessions, permission-scoped modules; configurable OTP MFA |
| Accounting and financial integrity | `content/zomorod-business/app.php` | Existing PHP ledger; transaction-safe payment/stock, POST+CSRF logout, explicit CLI-only initial DB setup |
| Django ERP and financial reports | `enterprise_portal/` | Multi-unit vouchers, budgets, inventory, contracts, projects, assets and trial balance; PHP source may be read **only** through CEO read-only bridge |
| Calendar and office automation | `enterprise_portal/calendar.py`, forms/templates | Permission-scoped month meetings/tasks, double-booking rejection, signed-in ICS export, task audit |
| Private correspondence + evidence | `enterprise_portal/private_uploads.py` | PDF/JPEG/PNG <=8 MiB, private 0700 directory, 0600 immutable UUID blobs, SHA-256 check on download, participant-based row-level access and independent upload/download permissions |
| CRM and marketing | `company_marketing/` | Unit-scoped leads and stage pipeline, campaign approval, publication planning, verified performance metrics |
| Messaging | `company_messaging/` | Consent-aware internal/outbound drafts, human approval and controlled dispatch |
| Master-agent and specialist desk | `ecosystem_hub/` | Human-authored natural-language routing to authorized specialists, deterministic read-only reports, optional audited tasks and task warnings |
| Private auctions | `content/zomorod-business/auctions.php` | Bid-free private opportunity register, role approval, internal documents; no official bid or transaction; PHP 8.3 needed |

**Not equivalent to a live autonomous AI service.** Agent reports and task-watch are bounded local code. No hosted LLM or verified hourly production scheduler is declared. No unattended payments, external bids or ad spend are allowed.

## Automation policy

1. User creates or authorizes a command. Permission, organizational unit, safe intent and request idempotency are checked.
2. Authorized specialist produces a local evidence-based report; optional internal task is created and audited.
3. Human reviews/approves potentially consequential changes. Scheduled watchers, when separately configured, may only generate local alerts and tasks.
4. Outbound messages, marketing publication, financial posting, inventory movement and auctions follow their separate approval and role gates. Autonomous publication/spending must remain disabled until verified policy and service authorizations exist.

## Offline verification

- `.github/workflows/zm-master-command-offline-ci-20261101.yml`: Django system check, schema/model migration consistency, office routes, ERP, calendar, attachments, CRM, messaging and agents.
- `.github/workflows/zm-unified-accounting-php-ci-20261101.yml`: PHP syntax, transaction and concurrency checks, CSRF logout HTTP regression, DB bootstrap gate, private auction suite.
- CI jobs must be **green for the exact integrated head SHA**; cancelled or superseded runs are not acceptable proof.
- Tests create only synthetic local data and never contact cPanel/VPS/production.

## Mandatory live-release gates — all remain HOLD unless proven

1. Owner-owned offsite backup **plus independently tested restore and rollback**, not merely backup-file existence.
2. Exact process-effective database file/inode/path observed from the cPanel Passenger/Django worker and cross-checked with configured application; no unverified switch from zero-byte Django DB to PHP ledger.
3. MFA/OTP enrollment, secure cookies, CSRF, staff roles and every sensitive row permission verified against the live environment.
4. PHP 8.3 + private auction routing validated on staging. Database change migrations reviewed and explicit; no implicit schema/seed on ordinary web traffic.
5. HTTPS/sessions/storage ACL and download tamper test validated on staging; attachment private directory **outside public_html** with 0700 permissions and protected backups.
6. Production smoke tests, owner signoff, immutable release SHA and proven rollback rehearsal.

Until all gates pass: **do not merge as a live release, deploy to public_html, modify production DB, delete historical templates/backups, restart the VPS factory, or enable outbound financial/marketing automation.** The VPS factory is **HOLD**; if required, the VPS may act only as an SSH relay to cPanel. Sites other than Zomorod are out of scope.

## Safe cleanup policy

Duplicate templates and old backups may be cataloged and hash-compared; deletion requires classification, a verified restorable owner-held copy, documented retention obligations and an exact allowlist of disposable paths. No blanket recursive removal. This staged branch performs **no production deletion**.

## Deployment operator checklist (after release gates)

- Confirm branch HEAD and both exact-head CI checks.
- Freeze/live snapshot and verify offline restore.
- Obtain read-only process-effective DB attestation.
- Confirm app secrets and MFA available via managed deployment configuration, not source.
- Run explicit reviewed migrations, PHP runtime preflight, security staging checks.
- Deploy in a rollback-capable window; verify permissions, finances, calendar, CRM, attachment download, marketing approval, master commands without sending or paying.
- Monitor logs and be prepared to restore last immutable release.

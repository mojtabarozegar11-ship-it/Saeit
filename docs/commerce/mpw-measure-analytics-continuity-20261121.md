# First-party analytics marker continuity — live repair 2026-11-21

## Incident

The first-party opt-in analytics initially installed on eight public static pages were silently lost from two high-value pages during a later content regeneration:

- /moj-prop/
- /moj-prop/starter-30-trx/

Live static files both contained zero tracker references, whereas the remaining six still contained one. Checkout endpoints returned HTTP 200; payment rendering and measurement readiness are distinct. No consenting visitor events were present in the private opt-in file at this checkpoint.

## Correction performed

A scoped repair script now inspects exactly eight known mojplaywin.com static HTML files and installs the marker only where missing. It verifies UTF-8, exactly one closing body tag, no duplicate/conflicting analytics tags, no symlinked pages, and a live tracker asset. Before mutating any page, it saves the current production bytes to a private 0700 backup directory with 0600 original files and a SHA-256 manifest. It rechecks the source hash before each atomic replacement to catch concurrent edits.

On 2026-11-21 at 03:29 UTC, only the two missing pages were modified. The other six pages were left byte-for-byte untouched. The repair was validated on disk and via HTTPS for all eight pages: exactly one /mpw-measure/tracker.js reference per page; tracker JS returned HTTP 200. Five targeted safety tests passed.

Private host backup:
/home/zomorod2/separated-backups/20261121/mpw-measure-static-repair-20261121T032951Z

## Runbook

Read-only status:
python3 scripts/mpw_measure_static_integrity.py

After authorization to deploy a scoped fix, on the cPanel host:
python3 scripts/mpw_measure_static_integrity.py --apply

Do not run --apply from untrusted paths. No cron-based rewriting of pages is installed. Other deployment pipelines regenerating these two HTML pages must preserve the analytics script tag to avoid a repeat. Treat a missing marker as an instrumentation outage, not evidence of zero visitors.

The script does not submit forms, create invoices, contact buyers, access email, modify Django, adjust gateway settings, update a database, restart Passenger, start the factory, or create a financial charge. Analytics still requires explicit browser consent and does not identify verified humans or demonstrate sales.

## Additional current read-only checkout audit

The live /mojprop-starter30-checkout/ shows one enabled POST form to the same path, with email, optional payer address, terms checkbox and CSRF. The /commerce/book/72/, /commerce/book/225/ and /commerce/book/879/ routes show enabled POST forms to their specific /commerce/trx-easy/start/<product>/ endpoints. These are only GET inspections; no order or payment was created. A valid form does not prove server-side transaction success.

## Caution

This script repairs marker loss, not consent gap, bot classification, true funnel linkage, server ledger proof, or sales acquisition. Other cycles may overwrite static pages again. The read-only status check must accompany static content releases or be integrated into their release gates.

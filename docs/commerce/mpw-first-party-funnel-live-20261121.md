# MojPlayWin + English MOJ PROP: first-party traffic and buy-intent measurement

**Live installation date:** 21 November 2026 UTC.  
**Scope:** https://mojplaywin.com/store/ and seven canonical static English MOJ PROP pages, including Starter30.  
**Owner objective:** distinguish lack of traffic from lack of checkout interest without counting bots, visits or clicks as a verified sale.

## Architecture

- First-party static JavaScript served at /mpw-measure/tracker.js.
- Explicit, optional opt-in consent, never initialized in other site sections.
- Source HTML pages only receive an external script tag; original layout and CTAs are not replaced.
- POST /mpw-measure/collect.php is same-origin-only and accepts a strict event/page allowlist.
- Output is JSONL under /home/zomorod2/.mpw-measure/events/ (0700 directory, 0600 new files). Nothing is published on the website.
- Random per-tab session ID persists in sessionStorage for at most 30 minutes of inactivity. It is not a user/account identity; no cookie is set by this tracker.
- The visitor may decline, or revoke permission through /mpw-measure/privacy.html.
- Only event name, approved page category, random session token, short UTM labels and server time are retained. No email, wallet, order number, invoice URL, transaction ID, user form data, full URL or raw IP is written to these JSONL records. Ordinary web-server access logs are distinct.
- Hard cap: 8 MiB of event data per UTC day. Collector failure does not interrupt navigation or payment. No external analytics vendor, API key, database migration, monthly fee or automation is required.

## Live pages (8)

1. /store/
2. /moj-prop/
3. /moj-prop/starter-30-trx/
4. /moj-prop/catalog/
5. /moj-prop/rules/
6. /moj-prop/payment/
7. /moj-prop/contact/
8. /moj-prop/signals/

**Important:** /store/ is actually served from public store/index.html by the current .htaccess fallback. Django's existing view_store logic does not measure that public landing. The public English MOJ PROP landing is also static. Do not assume the main repo's Django templates are the live public markup.

## What the numbers mean

- Page views: successful opt-in client page events, **not** all humans or all requests.
- Qualified/engaged session: opt-in session with an interaction or purchase-intent event. This is a **human-interest proxy**, not proof of a unique person; sophisticated bots can simulate clicks. Excludes unconsenting users, browser blockers and some legitimate passive visits.
- Buy click: same-origin link selected from public store to /commerce/book/:id/ or from MOJ PROP to Starter30 information/checkout.
- Drop-off proxy: opted-in engaged entry sessions without a later observed buy-click in the same browser tab. **Not** proof of customer abandonment and not a site-wide bounce rate.
- Checkout, invoice issuance, TRX payment, settlement and delivery: **not** inferred from a client click. Django checkout pages deliberately retain restrictive CSP and are not instrumented by this script. Authoritative server-side order/invoice/chain reconciliation is separately required before claiming actual conversions. The CLI report uses null (unknown) rather than zero for paid orders or uninstrumented checkout.
- Sources: UTM labels are meaningful only when campaign links contain safe UTM parameters; no visitor identity is retained in reports.

## Safe operational commands

Before deployment, on the authorized cPanel host with exact reviewed source in a private staging directory:

    php -l deploy/mpw_measure/collect.php
    node --check deploy/mpw_measure/tracker.js
    python3 -m unittest tests.test_mpw_measure_report
    python3 deploy/mpw_measure/install.py

After the scoped live installation:

    python3 scripts/mpw_measure_report.py --days 7
    python3 scripts/mpw_measure_report.py --days 30

Run the report from a protected local copy; it **never** prints session IDs. Empty files or zero observed events are not proof of zero visitors or zero sales.

## Deployment and rollback

The installer requires --apply, rejects symlinks/ambiguous HTML, checks all eight existing files before mutation, and backs up every replaced production file into a 0700 directory under /home/zomorod2/separated-backups/YYYYMMDD/. Writes are atomic. It does not touch .htaccess, database, WSGI, the factory, payment logic, account credentials, other sites or scheduled tasks.

Live backup: /home/zomorod2/separated-backups/20261121/mpw-measure-20261121T030040Z (backup time is UTC).

For a rollback, restore the eight backed-up HTML files only after a scoped review; removing new collector assets and historical private events is a separate approval-sensitive operation. No automatic deletion is performed. Retention policy and cleanup must be handled explicitly if analytics continues long-term.

## Acceptance evidence on 2026-11-21

- PHP parser and Node syntax checks passed.
- Three report unit tests passed.
- Installer preflight passed for 8 pages and 3 assets.
- Installer returned installed state and recorded all SHA256 values.
- Eight live page GETs returned 200 and each contained exactly one analytics script reference.
- JS and privacy pages returned 200.
- Collector GET returned 405; cross-origin invalid POST returned 403.
- /mojprop-starter30-checkout/, /commerce/book/72/ and /commerce/trx-easy/ GET remained HTTP 200.
- No synthetic conversion/purchase events were written. No claim of captured opted-in traffic or new paid orders yet.

**Next production measurement criterion:** at least one legitimate consenting visitor generates a non-PII event, followed by a refreshed report. Funnel ratios require organic observed cohorts. Verified invoice issuance/settlement needs a separate server ledger correlation pass.

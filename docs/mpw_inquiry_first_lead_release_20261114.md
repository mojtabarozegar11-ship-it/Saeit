# MojPlayWin — first qualified lead: bounded intake repair (2026-11-14)

**Source change only. Not approved for production deployment.** No customer
contact, email, SMS, purchases, payments, database writes, external publication,
new crons, new bots or financial commitments were performed by this work.

## Why this materially affects revenue

The existing twelve service pages contain quote-request links, but a visitor
must be able to complete a real first-party inquiry and reach a monitored
support address before a paid scoped service order is possible. A service
landing page with a 200 response, SEO tags or published prices is **not**
evidence of an actual lead or settled sale.

Two independently observed source defects:
1. The previous request size check depended on
   `strlen(CONTENT_LENGTH)>6`, which allowed a declared 12,001-byte request
   through even though the stated threshold was 12,000 bytes.
2. The source form, mailto fallback and two server-side page generators
   referred to the legacy `support@mojplaywin.com` address. The designated
   direct customer support mailbox for MojPlayWin is
   `mojplaywin@gmail.com`. Receipt/forwarding from the legacy address was
   **not** independently verified.

A third hardening observation: casting an array-valued incoming service/CSRF
field to string triggers PHP warnings and is unnecessary for honest buyers.
This PR fails closed on such malformed input without affecting a properly
completed request.

## Implemented source changes (exactly three previous owners + tests)

- `mpw_revenue_20261020/earn/inquiry.php`: single official customer support
  constant drives the customer-facing email fallback, extension-error
  fallback and inquiry notification destination.
- `oversized_inquiry_body`: pure PHP helper permits exactly the declared
  bytes 0 through 12000 and fails on 12001+, invalid numeric notation,
  excessive digit counts, embedded control characters and non-string input.
  Missing Content-Length remains subject to PHP's configured
  `post_max_size`; this helper alone cannot independently cap chunked uploads.
- CSRF still requires a verified string and `hash_equals` comparison.
  Service lookup refuses non-string slugs. The 13-key offer allowlist is
  unchanged.
- `scripts/mpw_revenue_integrated_upgrade_20261026.py`: fixes one
  generator-created legacy mailto fallback.
- `scripts/mpw_revenue_12_restore_20261026.py`: fixes both other legacy
  mailto fallbacks. Do not run these historic publishers without inspecting
  ownership, backup, and the active source version.
- `tests/test_mpw_inquiry_first_lead_20261114.py`: 32 isolated regression
  cases, including PHP CLI boundary executions, syntax lint, official support
  consistency and existing CSRF/consent/encryption/anti-spam/receipt guards.

**Intentionally preserved:** private AES-256-GCM inquiry record, reference
receipt, HTTPS-only session cookie attributes, CSRF, consent, valid reply
email, honeypot, 90-second rate limit, no credentials in public reports,
owner dispatch separation and no automatic binding quotation or payment.
These are not discretionary commercial obstacles.

## Source vs live route mapping

- In the repository, twelve pages link to
  `/earn/inquiry.php?service=<slug>`.
- The release transformer
  `scripts/mpw_revenue_integrated_upgrade_20261026.py` rewrites source
  `/earn/` URLs to `/mpw-editorial/revenue/`.
- The actual form action in the source is
  `/mpw-editorial/revenue/inquiry.php`, the mapped public target.
- `mpw-inquiry-cookie-session-repair-20261026.yml` checks the session cookie
  path, while its production repair job only executes on `main`. A Draft PR
  must not invoke a production repair.
- This mapping is **repository intent**, not an authenticated observation
  of currently serving Apache/LiteSpeed/Passenger/PHP files.

## Verification completed and what's missing

Source regression and syntax checks are to be correlated to the PR's **exact
commit SHA**. A green test result is NOT a live request or new revenue.
Direct external GET attempts to both `/earn/inquiry.php` and the
`/mpw-editorial/revenue/inquiry.php` path could not be verified through
the available browsing tool. Do not interpret that as a verified outage.

Minimum separately authorized production acceptance:
1. Read-only authenticated ownership/source mapping on cPanel; verify exact
   active PHP file SHA-256 and identify its rollback point.
2. Verify web server routing for live inquiry page and sample service page
   using safe **GET only**; confirm HTTPS, 200, expected form, CSRF field,
   official Gmail fallback and cookie path, without sending contact data.
3. Check private owner intake and dispatch **aggregate metadata only**:
   stored leads, timestamp, queue health, notification failures. Do not
   copy buyer emails/contents into CI, issues or public logs.
4. On separately approved staging, validate valid consent/CSRF, invalid
   email/oversized payload rejection and idempotent reference receipt; do
   not use real customer records or send test messages to production.
5. Before any production write, request case-specific owner approval,
   immutable backup, rollback, and exact allowed file list.
6. Count an actual **lead** only after an authorized, privacy-preserving
   intake receipt. Count a **sale** only when the written quote is accepted,
   payment legally settled and exact QC-approved deliverable privately
   delivered to the client.

## Release status

- GitHub source correction: **proposed (Draft PR)**.
- New live inquiry form deployed: **NOT VERIFIED**.
- Official Gmail delivery/forwarding from PHP mail: **NOT VERIFIED**.
- Production cPanel/host SHA, active private lead count: **UNKNOWN**.
- Settled revenue and paid deliveries: **UNKNOWN**.
- Additional spending, email, payment, deployment: **NONE EXECUTED**.
- Canonical operational agent remains `mojtaba.bot.ai`; this patch creates
  zero parallel agents and does not manipulate the current scheduler topology.

Do not remove rate-limit, consent, product rights, payment validation, staging,
backup, domain/email authentication or owner approval gates to raise a
completion percentage. The business acceptance criterion remains real,
reconciled, paid and fulfilled work.

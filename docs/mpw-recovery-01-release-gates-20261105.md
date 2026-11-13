# MojPlayWin — current release contract: guest TRX checkout without email
**Supersedes the archived email-recovery design below. Status: draft, not deployed. Updated 2026-11-12.**

## Historical cPanel source-versus-running-process discrepancy — evidence dated 2026-11-02

The customer's already-sent hosting-support correspondence records the
following *dated* source/Passenger observations. **These are not live
observations from 2026-11-12 and must not be promoted to current facts.**

- The file `/home/zomorod2/Saeit-staging/config/urls.py` reportedly
  contained the route `/commerce/trx-easy/purchases/`, and
  `services/mpw_trx_public_pages.py` invoked `patch_public(globals())`.
  The public endpoint nevertheless returned an HTTP 404 in an earlier check.
- The public `.htaccess` used a `PassengerAppRoot` under
  `/home/zomorod2/mojplaywin.com`; its `passenger_wsgi.py` reportedly
  loaded Django source from `/home/zomorod2/Saeit-staging`. This can be an
  intentional architecture, **not by itself proof of misconfiguration**.
  Actual running process, URLconf and worker version remain unverified.
- The guest adapter SHA-256 previously observed on cPanel was
  `79815303f4852d62f4d13b428805edc35b0d47f1135cab73094946c0f2326dc9`.
  This differs from the reviewed current candidate
  `11b0aa037c31fbcd1198331444d88426d9b4722d13606a7fda846c8f7601d949`.
  This **does not prove** that the old file still runs today.
- The historical public stderr log included `Reached max children process
  limit: 6 ... current: 8` and `io.UnsupportedOperation: fileno`.
  There is no timestamp-correlated proof these messages caused the checkout
  404 or sale failure; investigation must not silently conflate LSAPI
  process limits with Passenger/Django request routing.

**Next authorized read-only evidence required:** verify process-to-source
mapping, current file hashes, resolved URLconf and invoice recorder source
against actual serving worker identity, and timestamp-correlated error logs.
The existing audit script records **source-on-disk only** and cannot make
claims about in-memory Passenger worker versions. No reload, publish, source
copy, payment, ticket, or firewall modification is authorized here.

## Hosting-provider evidence and network root cause — 2026-11-12

The hosting provider's **existing** support replies were inspected read-only;
no ticket or email was sent. These are provider assertions, not proof of
reachability from a GitHub runner.

- Ticket **666685**, dated 2026-11-11: two separate services. VPS SSH port
  **22** on `178.239.147.150`; Python shared-host SSH port **1396**.
  The Python host requires the *connecting source IP* to be allowlisted.
- Ticket **419805**, dated 2026-11-12: provider replied "**انجام شد، بررسی
  بفرمایید**" to the request to allow SSH **from the VPS static IP to the
  Python host**. This does **not** allow all transient GitHub runner IPs.
- Ticket **864652**, dated 2026-11-09: provider demonstrated successful SSH
  to the VPS from its own network. It does not establish GitHub-runner access.
- GitHub Actions audit run **43242036979**: from the runner, host-key
  acquisition failed for direct Python-host SSH port **1396**, then for VPS
  SSH port **22**. These failed paths must not be reclassified as healthy.
- Technical implication: do not swap SSH ports or disable host identity
  verification. Existing provider policy favors an authorized **VPS-to-host**
  hop; the separate runner-to-VPS ingress remains unproven. Prefer the
  previously established owner-authorized hosting portal or an authenticated
  route with verifiable network origin to perform a bounded source audit.
- No more unattended runner SSH retries are authorized until an access path
  is demonstrably reachable. The existing source-audit workflow stays manual.

**Commercial continuity:** The provider sent an expiry reminder for
`mojplaywin.com` with a **2026-12-07** due date. Check renewal status
through the existing authenticated provider portal; no payment, auto-renewal
or financial obligation is approved in this PR.

## Read-only production source audit evidence — 2026-11-12

**Observed, not inferred:**

- Branch-only, bounded source-audit code was registered under
  `scripts/mpw_live_invoice_source_audit_readonly_20261112.py`.
  Its eight offline contract tests pass. It does not run Django or inspect
  a live invoice unless SSH actually succeeds.
- GitHub Actions run
  [43241620015](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43241620015):
  the first host-key acquisition step failed before reading source files.
- GitHub Actions run
  [43242036979](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43242036979):
  direct cPanel host-key scan at the currently configured port 1396 returned
  `MPW_CPANEL_DIRECT=HOST_KEY_UNREACHABLE`;
  VPS relay port 22 returned
  `MPW_VPS_RELAY=PORT22_HOST_KEY_UNREACHABLE`.
  The step exited with code 11. This establishes network/SSH reachability
  failure **from those GitHub runners only**, not a cPanel or VPS outage.
- SSH key secret variables were supplied (redacted in Actions logs).
  **Neither remote file was read; neither server fingerprint was verified in
  the failing run.** Do not claim source inspection or safe release.
- Previously verified isolated guest QA completed **110/110 tests** in
  [run 43241283448](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43241283448).
  These are source/offline tests, not real purchase receipts.

**Remaining gate:** Establish an authorized path to read the existing cPanel
Passenger/Django invoice sources and exact `record_invoice` dependencies.
Verify the actual current SSH ports and allowed ingress from the hosting
provider's already available dashboard/support history, or use a separately
approved authenticated hosting interface. Do **not** guess ports, bypass
host-key verification, alter firewall rules blindly, send a ticket/email,
deploy, merge, or move funds as part of this audit.

**Cost control:** Retire automatic network retry from PR pushes while both
observed SSH routes remain unreachable. Preserve the manual read-only audit
for later, after authorized network preconditions are confirmed.



> CAUTION: The old `MPW-RECOVERY-01` email capture, SMTP authorization,
> email claim migration, and email recovery activation sequence below is historical.
> **Do not execute it** for the current no-email guest checkout release.
> Keep it only as an audit trail. This section is the operative release policy.

## Required customer experience

- Buyers of products **72, 225, 879** can start a TRX invoice as guests with **no email field** (neither required nor optional) and without account signup or login.
- CSRF protection and the existing secure invoice, TRON chain-finality, ledger,
  fulfillment, product-rights and private-download authorizations remain in force.
- A unique unprivileged password-disabled guest identity and signed HttpOnly/Secure
  owner cookie are the candidate mechanism. Cookie presence **does not** prove a
  settled payment; an invoice/receipt/download must remain independently authorized.
- The owner cookie has a finite expiry and is browser-specific. If lost or expired,
  private orders must **not** be revealed using only a public transaction hash,
  order number, or claimed wallet address. Independent ownership verification and
  a safe recovery procedure are still required before commercial readiness.
- **PICM has been retired** and must not be in a required availability gate.

## Evidence versus release status

1. **GitHub tests** establish only candidate-code behavior. Green CI is neither
   deployment evidence nor proof of sale.
2. **GET-only live evidence** must establish a same-form POST action for each SKU,
   a valid CSRF token, the invoice CTA and no email input. It must independently
   flag the static storefront fallback. Public GET success is not payment proof.
3. **Read-only cPanel contract inspection** must establish the *actual* deployed
   Passenger app root, checkout template, guest adapter, invoice recorder
   (`record_invoice` and all invoked external helpers), database schema,
   and private rights/assets. Unknown code or any email-required invoice path
   is a **hard stop**, not an invitation to bypass or relax a guard.
4. **Backups and restore evidence** are required before mutation: private source
   snapshots, consistent MariaDB backup, verified restore capacity, rollback
   manifest and exact file hashes. Preserve existing orders and customers.
5. **Preflight and staging** must use reviewed, hash-bound source and the intended
   cPanel virtualenv, with zero live writes in preview. The separate
   `scripts/mpw_guest_checkout_live_release.py` and
   `scripts/mpw_guest_no_email_release.py` controllers have independent
   contract checks; do not assume either is safe or applicable until the live
   source baseline and operation order are verified.
6. **Separate owner approval** is required for production deployment. After a
   gated release, check the three public pages, CSRF-protected invoice POST in
   an authorized controlled context, Passenger reload, no-email order creation,
   TRX settlement finality, receipt ownership and private-download access.
7. A genuine paid end-to-end test is a **separate, explicitly approved** action:
   no fabricated payment, reused TX hash, wallet movement, email dispatch,
   or assertion of revenue based on test-only invoices.
8. Any failure triggers fail-closed diagnostics and, where applicable, only
   hash-checked rollback from the exact private backup. Never erase order,
   payment or fulfillment history.

**Current outstanding gates:** cPanel invoice recorder and schema unverified;
legacy email field reported on live product pages; live guest POST and paid
receipt recovery unverified. PR #1890 remains a draft until these are resolved.
No production deployment, database mutation, email or payment is authorized
by these instructions.

---

## Archived specification — do not execute for current no-email policy

# MPW-RECOVERY-01 — production release and rollback contract

This change is **source-staged only**. The branch does not migrate, deploy,
email, or touch MojPlayWin production records. GitHub is for source transfer;
the runtime is the existing Passenger/Django application on cPanel.

## Buyer journey

1. A new guest submits a validated email alongside the existing TRX invoice
   form. A Django `post_save` hook records an immutable, order-specific claim
   inside the invoice-creation transaction, then verifies the redirected
   `PaymentIntent` belongs to the same guest and matches the claim.
2. An existing unpaid invoice can be reused **only** with its matching claim.
   Legacy orders without a claim are never retroactively assigned to an email.
3. `/commerce/trx-easy/recover/` accepts a purchase email and always presents
   the same message regardless of whether it belongs to an eligible order.
   An SMTP action can occur only if **both** recovery routes and the independent
   owner approval flag are enabled.
4. The email contains a 256-bit, 15-minute one-time **code**, not a token URL.
   Only SHA-256 of the code is retained. POSTing the code consumes it under a
   database row lock. A secure, HttpOnly, 15-minute recovery cookie then scopes
   access to paid claims for that verified email.
5. Only orders with an independently verified finalized TRON receipt, matching
   ledger credit, and **all** line items in `CommerceFulfillment.ready` appear.
   Download delegates directly to the already deployed inner private handler
   `_download_paid`, because the public wrapper requires the original guest
   cookie that the buyer is explicitly recovering from. Email ownership,
   finality and fulfillment are checked again *before* delegation; the inner
   handler retains its original order-owner and private-file protections.
   The release preflight rejects a missing or renamed inner delivery handler.

## Required gated production sequence — NOT EXECUTED

1. Confirm the live `core.Order`, `core.PaymentIntent`, `OrderItem`,
   `CommerceFulfillment.item`, `core.crown_tron_receipts`, and the existing
   guest adapter match the audited contracts and inspect the exact live URL
   assembly. Do not use an unreviewed full-file overwrite.
2. Verify cPanel backups and exact SHA-256 snapshots of the *live* files.
   Preserve source backups outside the public web root. Before any schema
   migration, obtain a **fresh, consistent MariaDB SQL backup** through the
   approved private backup path and independently document a restore rehearsal.
   This release does **not** create a backup or prove its restore works.
   Confirm free space on both the primary host and backup destination.
3. Stage only the reviewed new module, models import, migration 0040, settings
   flags and guest adapter changes. Keep both new flags **false**.
   The source-controlled guard is
   `scripts/mpw_recovery_guarded_release_20261105.py`. Stage it in a private
   directory with the five pinned source files and their repository-relative
   paths, then invoke it with cPanel's existing Python 3.11 virtualenv:

   ```
   python -B release.py preflight /path/to/private/stage
   python -B release.py publish /path/to/private/stage RUN_ID DB_BACKUP_SHA256
   python -B release.py verify
   ```

   `RUN_ID` must be 8–20 decimal digits. `publish` is blocked unless a
   consistent full SQL gzip dump has *already* been placed at
   `/home/zomorod2/.local/share/mpw-recovery-01-release/db/RUN_ID.sql.gz`,
   with root/private folder permissions `0700`, file permissions `0600`,
   owned by the cPanel user, no symlinks or hardlinks, modified within
   the previous 24 hours, and SHA-256 exactly matching the separately
   established `DB_BACKUP_SHA256`. The controller reads the whole gzip
   stream to validate its CRC and checks for basic SQL/table markers; these
   checks are **not** a substitute for a successful database restore drill.
   A single run's exact-source snapshot is retained privately. These commands
   are documented for the authorized
   GitHub Actions → fingerprint-pinned SSH relay → cPanel path, not for a public
   URL or an untrusted shell.
4. Run `python manage.py migrate core 0040 --plan` for inspection **before**
   `publish`; the guarded `publish` command performs that migration once after
   passing the backup and source preflight. Do not manually repeat it. Use a
   maintenance window and known restorable backup. Confirm three new tables exist and
   that other core migrations remain unchanged. Never backfill old orders.
   The controller rejects any applied `core` migration numbered `0040` or newer
   other than this exact recovery migration, including unexpected `0041+`
   migrations. Investigate that condition explicitly; never fake or rewrite
   Django migration history to bypass this gate.
   The three recovery models intentionally define no Django admin permissions;
   the isolated migration verified that zero permissions are generated for them.
5. Run `python manage.py check`, a read-only route resolver check and a complete
   **rolled-back** transaction for new-order email binding. Verify a genuine
   existing unpaid invoice has unchanged behavior before enabling public use.
   Verify that cPanel's trusted `REMOTE_ADDR` represents distinct client IPs
   for rate limiting; do not trust arbitrary `X-Forwarded-For` headers.
6. With owner approval, set `MPW_GUEST_RECOVERY_ENABLED=true` while
   `MPW_GUEST_RECOVERY_EMAIL_APPROVED=false`, restart Passenger via its actual
   public app root, and perform GET/POST smoke checks **without sending email**.
   During this period the recovery UI clearly states that it is unavailable;
   the normal support path stays visible.
7. **Separate explicit owner approval** is required to set
   `MPW_GUEST_RECOVERY_EMAIL_APPROVED=true` and send even the first real
   recovery email. Use a controlled real order and test download after code
   entry. Do not fabricate a payment or report a simulated purchase as revenue.
8. Schedule `manage.py mpw_purge_recovery_ephemeral` daily through cPanel cron;
   it removes only expired codes and rate buckets, not order-email claims.

## Failure and rollback

- Gate fail, unexpected route, missing email input, reused unclaimed invoice,
  missing ledger/finality/fulfillment, missing schema, or SMTP problem: **deny**
  recovery and preserve checkout and payment history.
- First disable both feature flags and restart Passenger. If a source rollback
  is needed, restore each file from its verified private snapshot only if its
  current SHA-256 still matches the release manifest. Never overwrite newer
  edits. Keep recovery tables and claims intact so rollback never deletes
  customer data; a later controlled schema rollback needs its own backup.
  The controller's source rollback command is `python -B release.py rollback
  RUN_ID`. It refuses to overwrite any newer source edit and preserves all
  recovery tables, even if their migration completed before a source failure.
- Existing legacy paid orders whose email was not bound at the time of sale
  require manual invoice/transaction ownership verification. No bulk mapping
  from the mutable `auth.User.email` column is permitted.
- Runtime email delivery and successful third-party customer downloads remain
  **unproven** until the separately approved live acceptance check succeeds.

## Local evidence (isolated database)

```
PYTHONPATH=/tmp/mpw-django-libs:. python -m unittest tests.test_mpw_email_recovery_20261105 -v
python scripts/test_mpw_guest_first_order_identity.py
```

The test settings use only an in-memory SQLite database and a local-memory
email backend; no TRX transfer or SMTP network call is made.

The repository's pre-existing model/migration mismatch for older knowledge
models causes a separate `makemigrations --check` warning; do not generate or
apply that unrelated destructive model-removal migration as part of this task.

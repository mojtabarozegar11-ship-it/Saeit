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
   Download delegates to the already deployed private download handler, never
   exposes a filesystem path, and rechecks finality and email ownership.

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

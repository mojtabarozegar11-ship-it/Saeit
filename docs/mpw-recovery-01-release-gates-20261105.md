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
   Preserve source backups outside the public web root and take a database
   backup before a migration. Confirm free space and recoverability.
3. Stage only the reviewed new module, models import, migration 0040, settings
   flags and guest adapter changes. Keep both new flags **false**.
4. Run `python manage.py migrate core 0040 --plan`, then migrate on cPanel with
   a maintenance window and known backup. Confirm three new tables exist and
   that other core migrations remain unchanged. Never backfill old orders.
5. Run `python manage.py check`, a read-only route resolver check and a complete
   **rolled-back** transaction for new-order email binding. Verify a genuine
   existing unpaid invoice has unchanged behavior before enabling public use.
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

# Starter30 migration 0048 — isolated acceptance protocol (NOT release authorization)

Scope: `core.0048_mojprop_starter30_order`, native 30,000,000 SUN educational Starter30 only. No funded trading challenge. This protocol must **not** be run on the live shared Passenger database. Never remove or weaken the LIVE migration guard to make CI pass.

## Preconditions (all mandatory)

1. Pin and record the exact Saeit commit SHA, `core/migrations/0048_mojprop_starter30_order.py` Git blob SHA and Python/Django/MariaDB versions.
2. Obtain an independently verified full **production DB + application + media** backup with inventory, checksums, storage isolation, owner authorization, timestamp and retention. A two-public-file copy does not qualify.
3. Create a separate isolated database and separate credentials; confirm hostname, database name and account are **not** production or any other tenant. Never reuse a production DB password in CI logs.
4. Restore the complete backup to that isolated target, independently verify table counts and representative integrity checks, and record the restore evidence. No destructive operation against the live database.
5. Verify independent tenant routing/Passenger WSGI paths, static/media boundaries and the absence of push-triggered publication before any later release consideration.

## Exact-head acceptance sequence on isolated restore only

- Run `python manage.py showmigrations core` against the isolated database and record that 0047 is applied and 0048 is not.
- Run `python manage.py makemigrations --check --dry-run` against the pinned source and record zero model/schema drift.
- Run `python manage.py migrate core 0048 --plan` and inspect every planned operation; abort if any unrelated app, destructive data migration or tenant schema is affected.
- Run `python manage.py migrate core 0048 --noinput` **only in isolated restored DB**. Capture exit status, migration recorder row, table definitions, indexes and check constraints from the actual target MariaDB.
- Verify `order_ref` unique, `(network, txid)` exclusivity semantics (current source uses global unique `txid`), one-to-one `order`, fixed SKU, 30,000,000 SUN, merchant identity, `tron-mainnet`, `status=draft`, and `claim.state=unverified`. Attempt invalid rows inside a rollback-only transaction; assert they are rejected by MariaDB, not merely by Django `full_clean`.
- Verify no source-only row can become `issued`, `settled` or `delivered` by `QuerySet.update()` or direct SQL. No customer, payment, invoice, receipt or entitlement must be created as part of the test.
- Verify repeated migration is idempotent (`migrate core 0048` again) and `showmigrations` records the correct leaf.
- Take a second isolated snapshot, then test rollback to `core 0047` **only on a disposable clone**. Verify reverse plan removes only 0048-created tables/constraints, never existing order/payment records. Because reversing a create-table migration destroys its tables, any real populated 0048 deployment requires an explicit forward-fix/data-preservation plan, not blind rollback.
- Restore the disposable clone again and verify counts/checksums. Record the recovery duration and evidence link.

## Fail-closed acceptance decision

Any failed prerequisite, schema mismatch, untested rollback, missing legal seller identity, unverified merchant wallet, missing independent TRON finality, missing anti-replay ledger, missing buyer rights/consent, or incomplete exact-head CI means **NO MERGE / NO DEPLOY / NO PAYMENT**. Green source-only tests do not establish live restore or production readiness. Coordinate order/invoice invariants with cycle B and TXID/settlement ledger invariants with cycle C. Record all evidence in owner-private PR #102, not public customer-identifying logs.

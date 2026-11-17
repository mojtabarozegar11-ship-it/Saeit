# MOJ PROP Plan1 — MariaDB read-only prerequisites & approved isolated rehearsal

**Status:** Source-only tooling on Draft PR #2684. **NO-GO for production schema changes**.
**Scope:** `MOJ-PROP-01` v1.4.1; not the educational `MOJPROP-STARTER30`.

## 1. Manual READ-ONLY command, only on an authorized Django environment

Use a DB connection alias pointed at a privately controlled, authorized MariaDB
database with a least-privilege SELECT-only user:

```bash
python3.11 -B manage.py mojprop_v141_db_preflight --database default
```

**Do not use this example unchanged if `default` points to production.** Select
an authorized separately provisioned development alias, for example:

```bash
python3.11 -B manage.py mojprop_v141_db_preflight --database mojprop_dev
```

The command reads exactly three queries through the configured Django
connection: metadata `SELECT VERSION(), DATABASE(), ...`, applied
`django_migrations` names for parent `0008_prospect_contact_intake` and
target `0009_v141_sim_replay_journal`, and table names/storage engines from
`information_schema.tables`. It checks MariaDB >=10.6, default InnoDB,
strict SQL mode, Django transaction support and `SELECT FOR UPDATE` feature
support; reports migration state as `PENDING` or `APPLIED`. It does not
create an environment, database, user, schema or backup, and does not invoke
`migrate`, `sqlmigrate`, a schema editor, SQL DDL or writes.

**The result always carries:**
`migration_authorized=false` and `release_authorized=false`.
A passing probe does not certify backup, restoration, disk capacity,
concurrent DB writes, real brokerage or legal commerce.

Error reports never include driver exception strings, credentials or
database names. Prefer executing from a protected operator console; never
paste connection secrets into GitHub issues, PR comments or chat.

## 2. Hard prerequisites BEFORE migration rehearsal or production

1. Independently verify ownership and source of complete site-code/database
   backup, store securely **outside the host** with cryptographic digest and
   demonstrate restoration onto an isolated development database.
2. Measure the REAL database server's free bytes and expected migration disk
   footprint. Prior reports of a nearly full VPS are historical and MUST NOT
   be treated as current measurements.
3. Identify Django project settings/database alias and MariaDB version on
   the target database with a credential-managed, least-privilege read-only
   operator account. Confirm `0008` is actually applied and no unknown
   `PropV141SimState` / `PropV141SimReceipt` tables exist.
4. Require approval before *any* schema change or deployment, even on a
   shared live database. Existing v1.2 buyer enrollments must remain untouched.
5. Only after prior conditions: separately authorize a **development**
   migration of `0009_v141_sim_replay_journal`, prove reversible migration
   behavior, uniqueness constraints, proper InnoDB locks, interleaved
   multi-connection sequence increments, failed transaction rollback, receipt
   tampering detection and backup restoration.
6. Preserve the complete signed RAW simulator manifest and immutable
   independently anchored receipts outside MariaDB. A local SHA256 chain does
   NOT prove an entire journal wasn't rewritten by a privileged DB actor.

## 3. Actual execution and evidence

- [619 successful source-only tests](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44132781181) at the preceding revision.
- [654 successful Python 3.11 tests](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44134486756) at `32786e1558c872aaac7be2e440d2f0e6db18e019`; contains 35 read-only query tests with a fake database connection. It does **NOT** contain a live MariaDB transaction test.
- On the ChatGPT execution container during this review, Python was 3.13 and
  Django, PyMySQL and local MariaDB/MySQL server binaries were absent; a free
  package install could not reach the package index (DNS unavailable).
  Therefore **zero actual MariaDB migration/concurrency/restore runs were completed**.

## 4. Release status (hard stop)

No verified lawful signed customer contract, refund/KYC/AML signoff,
validated 30 native TRX = 30,000,000 SUN payment settlement,
authorized LiteFinance third-party trade rights or proved real USD 100 reserve,
authentic complete simulator feed, independently verified Instagram **OR**
Facebook post for 672 hours, restored full off-host backup, or production
release authorization exists in the evidence reviewed here.

**RELEASE = NO-GO.** The new diagnostic command is manual and read-only,
and must never be adapted to auto-run migrations or accept live orders.
